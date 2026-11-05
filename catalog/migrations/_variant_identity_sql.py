"""Variant-only guards; keep CINV-02's registry and sequence unchanged."""

REMOVE_LEGACY = """
DROP TRIGGER catalog_product_sku_guard ON catalog_product;
DROP TRIGGER catalog_product_sku_changed ON catalog_product;
DROP TRIGGER catalog_variant_sku_guard ON catalog_productvariant;
DROP TRIGGER catalog_variant_sku_changed ON catalog_productvariant;
DROP TRIGGER catalog_ordered_sku ON checkout_orderitem;
DROP FUNCTION catalog_guard_sku();
DROP FUNCTION catalog_sku_changed();
DROP FUNCTION catalog_ordered_sku();
DROP FUNCTION catalog_sku_available(text,bigint,bigint);
"""

INSTALL = """
CREATE FUNCTION catalog_sku_available(candidate text) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT NOT EXISTS (
        SELECT 1 FROM catalog_skuidentifier WHERE code=lower(btrim(candidate))
    );
$$;

CREATE FUNCTION catalog_guard_sku() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous text := ''; candidate text; generated boolean:=false;
    actor bigint := nullif(current_setting('retail.sku_actor',true),'')::bigint;
BEGIN
    PERFORM 1 FROM catalog_product WHERE id=NEW.product_id FOR UPDATE;
    IF TG_OP='UPDATE' THEN
        IF OLD.product_id<>NEW.product_id THEN
            RAISE EXCEPTION 'An issued SKU cannot be transferred' USING ERRCODE='23514';
        END IF;
        previous:=lower(btrim(OLD.sku));
    END IF;
    IF TG_OP='INSERT' AND btrim(NEW.sku)='' THEN
        NEW.sku:=catalog_next_sku();
        generated:=true;
    END IF;
    candidate:=lower(btrim(NEW.sku));
    IF TG_OP='UPDATE' AND previous=candidate THEN RETURN NEW; END IF;
    IF candidate='' OR (TG_OP='UPDATE' AND actor IS NULL) THEN
        RAISE EXCEPTION 'An issued SKU requires an authorized correction' USING ERRCODE='23514';
    END IF;
    PERFORM pg_advisory_xact_lock(734003020);
    IF TG_OP='UPDATE' AND (
        EXISTS (SELECT 1 FROM checkout_orderitem WHERE variant_id=NEW.id OR
            (product_id=NEW.product_id AND variant_id IS NULL)) OR
        EXISTS (SELECT 1 FROM catalog_skuidentifier
            WHERE variant_key=NEW.id AND ordered_at IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'The SKU is locked after its first accepted order' USING ERRCODE='23514';
    END IF;
    IF NOT catalog_sku_available(NEW.sku) THEN
        RAISE EXCEPTION 'This SKU was already issued and cannot be reused' USING ERRCODE='23505';
    END IF;
    INSERT INTO catalog_skuidentifier
        (code,product_id,variant_id,product_key,variant_key,issued_at,actor_id,actor_name,source)
    VALUES (candidate,NEW.product_id,NEW.id,NEW.product_id,NEW.id,clock_timestamp(),actor,
        coalesce(current_setting('retail.sku_actor_name',true),''),
        CASE WHEN generated THEN 'generated' ELSE
            coalesce(nullif(current_setting('retail.sku_source',true),''),'manual') END);
    RETURN NEW;
END;
$$;

CREATE FUNCTION catalog_sku_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE label text;
BEGIN
    IF lower(btrim(OLD.sku))=lower(btrim(NEW.sku)) THEN RETURN NEW; END IF;
    SELECT name INTO label FROM catalog_product WHERE id=NEW.product_id;
    INSERT INTO access_auditevent
        (actor_id,actor_name,occurred_at,action,module,target_id,outcome,details)
    VALUES (nullif(current_setting('retail.sku_actor',true),'')::bigint,
        coalesce(current_setting('retail.sku_actor_name',true),''),clock_timestamp(),
        'sku_corrected','catalog.productvariant',NEW.id::text,'success',jsonb_build_object(
            'target_name',label,'target_type','Product variant',
            'subject_module','catalog.product','subject_id',NEW.product_id::text,
            'changes',jsonb_build_object('SKU',
                jsonb_build_object('before',OLD.sku,'after',NEW.sku))));
    RETURN NEW;
END;
$$;

CREATE FUNCTION catalog_ordered_sku() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE candidate text:=lower(btrim(NEW.sku)); owner bigint:=NEW.product_id;
BEGIN
    IF NEW.variant_id IS NOT NULL THEN
        SELECT product_id INTO owner FROM catalog_productvariant WHERE id=NEW.variant_id;
        IF NEW.product_id IS NOT NULL AND owner IS DISTINCT FROM NEW.product_id THEN
            RAISE EXCEPTION 'Order variant belongs to another product' USING ERRCODE='23514';
        END IF;
    END IF;
    PERFORM 1 FROM catalog_product WHERE id=owner FOR UPDATE;
    PERFORM pg_advisory_xact_lock(734003020);
    IF candidate<>'' THEN
        IF EXISTS (SELECT 1 FROM catalog_skuidentifier WHERE code=candidate AND
            (product_key IS DISTINCT FROM owner OR
                variant_key IS DISTINCT FROM NEW.variant_id)) THEN
            RAISE EXCEPTION 'Order SKU ownership conflicts' USING ERRCODE='23514';
        END IF;
        INSERT INTO catalog_skuidentifier
            (code,product_id,variant_id,product_key,variant_key,
                issued_at,actor_name,source,ordered_at)
        VALUES (candidate,owner,NEW.variant_id,owner,NEW.variant_id,clock_timestamp(),'',
            'order',clock_timestamp())
        ON CONFLICT(code) DO UPDATE SET
            ordered_at=coalesce(catalog_skuidentifier.ordered_at,EXCLUDED.ordered_at);
    END IF;
    UPDATE catalog_skuidentifier SET ordered_at=clock_timestamp()
    WHERE ordered_at IS NULL AND (variant_id=NEW.variant_id OR
        (NEW.variant_id IS NULL AND product_id=owner));
    RETURN NEW;
END;
$$;

CREATE FUNCTION catalog_check_default() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner bigint;
BEGIN
    IF TG_TABLE_NAME='catalog_product' THEN owner:=NEW.id;
    ELSIF TG_OP='DELETE' THEN owner:=OLD.product_id;
    ELSE owner:=NEW.product_id;
    END IF;
    IF EXISTS(SELECT 1 FROM catalog_product WHERE id=owner) AND
        (SELECT count(*) FROM catalog_productvariant WHERE product_id=owner AND is_default)<>1 THEN
        RAISE EXCEPTION 'A product must have exactly one default variant' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION catalog_check_primary() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE option_id bigint;
BEGIN
    IF TG_OP='DELETE' THEN option_id:=OLD.variant_id; ELSE option_id:=NEW.variant_id; END IF;
    IF EXISTS(SELECT 1 FROM catalog_productphoto WHERE variant_id=option_id) AND NOT
        EXISTS(SELECT 1 FROM catalog_productphoto WHERE variant_id=option_id AND is_primary) THEN
        RAISE EXCEPTION 'A nonempty gallery requires a primary photo' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER catalog_variant_sku_guard BEFORE INSERT OR UPDATE OF sku,product_id
ON catalog_productvariant FOR EACH ROW EXECUTE FUNCTION catalog_guard_sku();
CREATE TRIGGER catalog_variant_sku_changed AFTER UPDATE OF sku ON catalog_productvariant
FOR EACH ROW EXECUTE FUNCTION catalog_sku_changed();
CREATE TRIGGER catalog_ordered_sku BEFORE INSERT ON checkout_orderitem
FOR EACH ROW EXECUTE FUNCTION catalog_ordered_sku();
CREATE CONSTRAINT TRIGGER catalog_product_default AFTER INSERT ON catalog_product
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION catalog_check_default();
CREATE CONSTRAINT TRIGGER catalog_variant_default AFTER INSERT OR UPDATE OR DELETE
ON catalog_productvariant DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION catalog_check_default();
CREATE CONSTRAINT TRIGGER catalog_photo_primary AFTER INSERT OR UPDATE OR DELETE
ON catalog_productphoto DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION catalog_check_primary();
"""

UNINSTALL = """
DROP TRIGGER catalog_product_default ON catalog_product;
DROP TRIGGER catalog_variant_default ON catalog_productvariant;
DROP TRIGGER catalog_photo_primary ON catalog_productphoto;
DROP TRIGGER catalog_variant_sku_guard ON catalog_productvariant;
DROP TRIGGER catalog_variant_sku_changed ON catalog_productvariant;
DROP TRIGGER catalog_ordered_sku ON checkout_orderitem;
DROP FUNCTION catalog_check_default();
DROP FUNCTION catalog_check_primary();
DROP FUNCTION catalog_guard_sku();
DROP FUNCTION catalog_sku_changed();
DROP FUNCTION catalog_ordered_sku();
DROP FUNCTION catalog_sku_available(text);
"""
