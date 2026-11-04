"""SQL for the durable registry migration."""

INSTALL = """
CREATE SEQUENCE catalog_sku_number AS bigint MINVALUE 1 NO CYCLE;

CREATE FUNCTION catalog_sku_available(candidate text, owner bigint, option_id bigint)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT NOT EXISTS (SELECT 1 FROM catalog_skuidentifier WHERE code = lower(btrim(candidate)))
    OR EXISTS (
        SELECT 1 FROM catalog_skuidentifier r
        WHERE r.code = lower(btrim(candidate)) AND r.product_id = owner
        AND (
            (option_id IS NOT NULL AND r.variant_key IS NULL AND EXISTS (
                SELECT 1 FROM catalog_product p WHERE p.id = owner AND lower(btrim(p.sku)) = r.code
            ))
            OR (option_id IS NULL AND EXISTS (
                SELECT 1 FROM catalog_productvariant v WHERE v.id = r.variant_id
                AND v.product_id = owner AND lower(btrim(v.sku)) = r.code
            ))
        )
    );
$$;

CREATE FUNCTION catalog_next_sku() RETURNS text LANGUAGE plpgsql AS $$
DECLARE number bigint; candidate text;
BEGIN
    PERFORM pg_advisory_xact_lock(734003020);
    LOOP
        number := nextval('catalog_sku_number');
        candidate := 'SKU-' || lpad(number::text, greatest(6, length(number::text)), '0');
        IF NOT EXISTS (SELECT 1 FROM catalog_skuidentifier WHERE code = lower(candidate)) THEN
            RETURN candidate;
        END IF;
    END LOOP;
END;
$$;

CREATE FUNCTION catalog_guard_sku() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    owner bigint; option_id bigint; previous text := ''; candidate text;
    actor bigint := nullif(current_setting('retail.sku_actor', true), '')::bigint;
    actor_name text := coalesce(current_setting('retail.sku_actor_name', true), '');
BEGIN
    IF TG_TABLE_NAME = 'catalog_product' THEN
        owner := NEW.id;
    ELSE
        owner := NEW.product_id;
        option_id := NEW.id;
        IF TG_OP = 'UPDATE' AND OLD.product_id <> NEW.product_id THEN
            RAISE EXCEPTION 'An issued SKU cannot be transferred to another product'
                USING ERRCODE = '23514';
        END IF;
        PERFORM 1 FROM catalog_product WHERE id = owner FOR UPDATE;
    END IF;
    candidate := lower(btrim(NEW.sku));
    IF TG_OP = 'UPDATE' THEN
        previous := lower(btrim(OLD.sku));
        IF previous = candidate THEN RETURN NEW; END IF;
    END IF;
    IF previous <> '' AND (candidate = '' OR actor IS NULL) THEN
        RAISE EXCEPTION 'An issued SKU requires an authorized correction' USING ERRCODE = '23514';
    END IF;
    IF candidate = '' THEN
        IF option_id IS NOT NULL THEN
            RAISE EXCEPTION 'A variant requires a non-empty SKU' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    PERFORM pg_advisory_xact_lock(734003020);
    IF TG_OP = 'UPDATE' AND (
        EXISTS (SELECT 1 FROM checkout_orderitem WHERE
            (option_id IS NULL AND product_id = owner) OR
            (option_id IS NOT NULL AND
                (variant_id = option_id OR (product_id = owner AND (variant_id IS NULL
                    OR EXISTS (SELECT 1 FROM catalog_product WHERE id = owner
                        AND lower(btrim(sku)) = previous)))))
        ) OR EXISTS (SELECT 1 FROM catalog_skuidentifier WHERE ordered_at IS NOT NULL AND
            ((option_id IS NULL AND product_key = owner) OR
                (option_id IS NOT NULL AND variant_key = option_id))
        )
    ) THEN
        RAISE EXCEPTION 'The SKU is locked after its first accepted order' USING ERRCODE = '23514';
    END IF;
    IF NOT catalog_sku_available(NEW.sku, owner, option_id) THEN
        RAISE EXCEPTION 'This SKU was already issued and cannot be reused' USING ERRCODE = '23505';
    END IF;
    INSERT INTO catalog_skuidentifier
        (code, product_id, variant_id, product_key, variant_key,
            issued_at, actor_id, actor_name, source)
    VALUES (candidate, owner, option_id, owner, option_id, clock_timestamp(), actor, actor_name,
        coalesce(nullif(current_setting('retail.sku_source', true), ''), 'manual'))
    ON CONFLICT (code) DO UPDATE SET
        variant_id = coalesce(catalog_skuidentifier.variant_id, EXCLUDED.variant_id),
        variant_key = coalesce(catalog_skuidentifier.variant_key, EXCLUDED.variant_key);
    RETURN NEW;
END;
$$;

CREATE FUNCTION catalog_sku_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner bigint; module text; label text;
BEGIN
    IF lower(btrim(OLD.sku)) = lower(btrim(NEW.sku)) THEN RETURN NEW; END IF;
    IF TG_TABLE_NAME = 'catalog_product' THEN
        owner := NEW.id; module := 'catalog.product'; label := NEW.name;
        IF btrim(OLD.sku) <> '' THEN
            UPDATE catalog_productvariant SET sku = NEW.sku, updated_at = NEW.updated_at,
                updated_by_id = NEW.updated_by_id
            WHERE product_id = owner AND lower(btrim(sku)) = lower(btrim(OLD.sku));
        END IF;
    ELSE
        owner := NEW.product_id; module := 'catalog.productvariant';
        SELECT name INTO label FROM catalog_product WHERE id = owner;
        UPDATE catalog_product SET sku = NEW.sku, updated_at = NEW.updated_at,
            updated_by_id = NEW.updated_by_id
        WHERE id = owner AND lower(btrim(sku)) = lower(btrim(OLD.sku));
    END IF;
    INSERT INTO access_auditevent
        (actor_id, actor_name, occurred_at, action, module, target_id, outcome, details)
    VALUES (nullif(current_setting('retail.sku_actor', true), '')::bigint,
        coalesce(current_setting('retail.sku_actor_name', true), ''), clock_timestamp(),
        'sku_corrected', module, NEW.id::text, 'success', jsonb_build_object(
            'target_name', label, 'target_type', CASE WHEN module = 'catalog.product'
                THEN 'Product' ELSE 'Product variant' END,
            'subject_module', 'catalog.product', 'subject_id', owner::text,
            'changes', jsonb_build_object('SKU',
                jsonb_build_object('before', OLD.sku, 'after', NEW.sku))
        ));
    RETURN NEW;
END;
$$;

CREATE FUNCTION catalog_ordered_sku() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE candidate text := lower(btrim(NEW.sku)); owner bigint := NEW.product_id;
BEGIN
    IF owner IS NULL AND NEW.variant_id IS NOT NULL THEN
        SELECT product_id INTO owner FROM catalog_productvariant WHERE id = NEW.variant_id;
    END IF;
    PERFORM 1 FROM catalog_product WHERE id = owner FOR UPDATE;
    PERFORM pg_advisory_xact_lock(734003020);
    IF candidate <> '' THEN
        IF owner IS NOT NULL AND EXISTS (
            SELECT 1 FROM catalog_skuidentifier
            WHERE code = candidate AND product_key IS DISTINCT FROM owner
        ) THEN
            RAISE EXCEPTION 'Order SKU ownership conflicts with the issued identifier'
                USING ERRCODE = '23514';
        END IF;
        INSERT INTO catalog_skuidentifier
            (code, product_id, variant_id, product_key, variant_key,
                issued_at, actor_name, source, ordered_at)
        VALUES (candidate, owner, NEW.variant_id, owner, NEW.variant_id,
            clock_timestamp(), '', 'order', clock_timestamp())
        ON CONFLICT (code) DO UPDATE SET
            ordered_at = coalesce(catalog_skuidentifier.ordered_at, EXCLUDED.ordered_at);
    END IF;
    UPDATE catalog_skuidentifier SET ordered_at = clock_timestamp()
    WHERE ordered_at IS NULL AND product_id = owner AND (
        NEW.variant_id IS NULL OR variant_key IS NULL OR variant_id = NEW.variant_id
        OR code = (SELECT lower(btrim(sku)) FROM catalog_product WHERE id = owner)
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER catalog_product_sku_guard BEFORE INSERT OR UPDATE OF sku ON catalog_product
FOR EACH ROW EXECUTE FUNCTION catalog_guard_sku();
CREATE TRIGGER catalog_variant_sku_guard BEFORE INSERT OR UPDATE OF sku, product_id
ON catalog_productvariant
FOR EACH ROW EXECUTE FUNCTION catalog_guard_sku();
CREATE TRIGGER catalog_product_sku_changed AFTER UPDATE OF sku ON catalog_product
FOR EACH ROW EXECUTE FUNCTION catalog_sku_changed();
CREATE TRIGGER catalog_variant_sku_changed AFTER UPDATE OF sku ON catalog_productvariant
FOR EACH ROW EXECUTE FUNCTION catalog_sku_changed();
CREATE TRIGGER catalog_ordered_sku BEFORE INSERT ON checkout_orderitem
FOR EACH ROW EXECUTE FUNCTION catalog_ordered_sku();
"""

UNINSTALL = """
DROP TRIGGER catalog_ordered_sku ON checkout_orderitem;
DROP TRIGGER catalog_product_sku_changed ON catalog_product;
DROP TRIGGER catalog_variant_sku_changed ON catalog_productvariant;
DROP TRIGGER catalog_product_sku_guard ON catalog_product;
DROP TRIGGER catalog_variant_sku_guard ON catalog_productvariant;
DROP FUNCTION catalog_ordered_sku();
DROP FUNCTION catalog_sku_changed();
DROP FUNCTION catalog_guard_sku();
DROP FUNCTION catalog_next_sku();
DROP FUNCTION catalog_sku_available(text, bigint, bigint);
DROP SEQUENCE catalog_sku_number;
"""
