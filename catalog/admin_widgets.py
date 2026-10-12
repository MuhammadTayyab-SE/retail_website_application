class PlainRelatedChoicesMixin:
    """Use plain dropdowns; manage related records from their dedicated screens."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and db_field.name in {"parent", "category", "product"}:
            for action in ("add", "change", "delete", "view"):
                setattr(field.widget, f"can_{action}_related", False)
        return field
