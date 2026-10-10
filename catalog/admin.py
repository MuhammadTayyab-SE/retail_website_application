from django.contrib import admin

from catalog.models import Category
from config.admin import site


@admin.register(Category, site=site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "position", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name"]
    list_editable = ["position", "is_active"]
    list_select_related = ["parent"]
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False
