from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminVisualIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            "visual-owner", "visual-owner@example.invalid", "synthetic-visual-owner-831!"
        )
        cls.parent = Category.objects.create(name="Fresh food")
        cls.child = Category.objects.create(name="<Seasonal>", parent=cls.parent, is_active=False)

    def setUp(self):
        self.client.force_login(self.owner)

    def test_dashboard_uses_database_counts_and_escapes_category_names(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "retail_admin/index.html")
        self.assertEqual(
            response.context["category_summary"],
            {"total": 1, "active": 0, "inactive": 1, "roots": 0},
        )
        self.assertEqual(response.context["parent_category_count"], 1)
        self.assertEqual(list(response.context["recent_categories"]), [self.child])
        self.assertContains(response, "&lt;Seasonal&gt;")
        self.assertNotContains(response, "<Seasonal>")
        self.assertContains(
            response, reverse("admin:catalog_category_change", args=[self.child.pk])
        )

    def test_shared_shell_renders_across_management_and_account_pages(self):
        urls = [
            reverse("admin:index"),
            reverse("admin:app_list", kwargs={"app_label": "catalog"}),
            reverse("admin:catalog_category_changelist"),
            reverse("admin:catalog_category_add"),
            reverse("admin:catalog_category_change", args=[self.parent.pk]),
            reverse("admin:catalog_category_history", args=[self.parent.pk]),
            reverse("admin:password_change"),
            reverse("admin:settings"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/base_site.html")
                self.assertContains(response, "body.retail-admin {")
                self.assertContains(response, "--sidebar-bg:#172638")
                self.assertContains(response, 'class="retail-admin ')
                self.assertContains(response, 'aria-label="Store navigation"', count=1)
                self.assertNotContains(response, 'class="retail-shortcuts"')
                self.assertNotContains(response, "admin/css/nav_sidebar.css")
                self.assertContains(response, 'id="logout-form"')

    def test_invalid_category_submission_retains_shell_and_error_feedback(self):
        response = self.client.post(
            reverse("admin:catalog_category_add"), {"name": "", "position": -1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertTemplateUsed(response, "admin/base_site.html")
        self.assertEqual(Category.objects.count(), 2)

    def test_logout_keeps_shell_and_clears_session(self):
        response = self.client.post(reverse("admin:logout"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/base_site.html")
        self.assertNotContains(response, 'aria-label="Store navigation"')
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_parent_creation_is_independent_even_with_submitted_parent(self):
        url = reverse("admin:catalog_category_add") + "?kind=parent"
        response = self.client.get(url)
        self.assertContains(response, "Add parent category")
        self.assertNotContains(response, 'id="id_parent"')
        response = self.client.post(
            url,
            {"name": "Pantry", "parent": self.parent.pk, "position": 0, "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Category.objects.get(name="Pantry").parent_id)
        self.assertTrue(Category.objects.get(name="Pantry").is_parent_category)

    def test_category_creation_allows_optional_parent(self):
        url = reverse("admin:catalog_category_add")
        response = self.client.get(url)
        self.assertContains(response, "Parent category (optional)")
        self.assertFalse(response.context["adminform"].form.fields["parent"].required)
        for name, parent in (("Independent", ""), ("Grouped", self.parent.pk)):
            with self.subTest(parent=parent):
                response = self.client.post(
                    url, {"name": name, "parent": parent, "position": 0, "_save": "Save"}
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Category.objects.get(name=name).parent_id, parent or None)

    def test_parent_choices_exclude_regular_categories_and_reject_forged_ids(self):
        regular = Category.objects.create(name="Independent category")
        empty_parent = Category.objects.create(name="Empty parent", is_parent_category=True)
        url = reverse("admin:catalog_category_add")
        for form_url in (url, reverse("admin:catalog_category_change", args=[regular.pk])):
            response = self.client.get(form_url)
            choices = response.context["adminform"].form.fields["parent"].queryset
            self.assertEqual(set(choices), {self.parent, empty_parent})
        response = self.client.post(
            url, {"name": "Invalid child", "parent": regular.pk, "position": 0, "_save": "Save"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("parent", response.context["adminform"].form.errors)
        self.assertFalse(Category.objects.filter(name="Invalid child").exists())
        response = self.client.post(
            url, {"name": "Valid child", "parent": empty_parent.pk, "position": 0, "_save": "Save"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Category.objects.get(name="Valid child").parent_id, empty_parent.pk)
        listing = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertEqual(set(listing.context["category_parents"]), {self.parent, empty_parent})

    def test_photo_editor_initialization_is_included_in_both_forms(self):
        for suffix in ("", "?kind=parent"):
            with self.subTest(suffix=suffix):
                response = self.client.get(reverse("admin:catalog_category_add") + suffix)
                self.assertContains(response, 'id="id_photo"', count=1)
                self.assertContains(response, "data-photo-image", count=2)
                self.assertContains(response, "URL.createObjectURL(file)")
                self.assertContains(response, 'type="range"', count=3)
                self.assertNotContains(response, 'src="/static/catalog/category_photo.js"')

    def test_category_table_filters_counts_and_read_only_status(self):
        url = reverse("admin:catalog_category_changelist")
        response = self.client.get(url)
        self.assertNotContains(response, '<nav class="retail-breadcrumbs"')
        self.assertNotContains(response, "Apply filters")
        self.assertContains(response, 'class="category-count">1</span>')
        self.assertContains(response, "Save order")
        self.assertNotContains(response, 'aria-label="Category pages"')
        formset = response.context["cl"].formset
        self.assertIn("position", formset.forms[0].fields)
        self.assertNotIn("is_active", formset.forms[0].fields)
        response = self.client.get(
            url, {"q": "Seasonal", "is_active__exact": "0", "parent__id__exact": self.parent.pk}
        )
        self.assertEqual(list(response.context["cl"].result_list), [self.child])
        self.assertContains(response, 'class="category-count">1</span>')
        response = self.client.get(url, {"q": "no-matching-category"})
        self.assertEqual(response.context["cl"].result_count, 0)
        self.assertNotContains(response, 'class="retail-button category-save"')

    def test_category_pagination_preserves_filters(self):
        Category.objects.bulk_create([Category(name=f"Bulk {i:02}") for i in range(28)])
        response = self.client.get(reverse("admin:catalog_category_changelist"), {"q": "Bulk"})
        self.assertContains(response, 'aria-label="Category pages"')
        self.assertContains(response, "p=2")
        self.assertContains(response, "q=Bulk")
        self.assertEqual(len(response.context["cl"].result_list), 25)
        self.assertContains(response, "Showing 25 of 28")

    def test_result_summary_matches_filtered_rows_and_empty_state(self):
        Category.objects.bulk_create(
            [
                Category(name="Active A"),
                Category(name="Active B"),
                Category(name="Inactive", is_active=False),
            ]
        )
        url = reverse("admin:catalog_category_changelist")
        response = self.client.get(url, {"is_active__exact": "1"})
        self.assertEqual(len(response.context["cl"].result_list), 2)
        self.assertContains(response, 'class="category-count">2</span>')
        self.assertContains(response, "Showing 2 of 2 &middot; 4 total")
        self.assertNotContains(response, "2 matching")
        self.assertNotContains(response, "status.textContent = summary.textContent.trim()")
        response = self.client.get(url, {"q": "Missing entry"})
        self.assertContains(response, 'class="category-count">0</span>')
        self.assertContains(response, "Showing 0 of 0 &middot; 4 total")

    def test_account_actions_are_in_sidebar_and_settings(self):
        response = self.client.get(reverse("admin:index"))
        html = response.content.decode()
        header = html.split('<header id="header">')[1].split("</header>")[0]
        self.assertNotIn("Sign out", header)
        self.assertNotIn("Change password", header)
        self.assertContains(response, '<details class="retail-sidebar-account">')
        self.assertContains(response, 'action="/admin/logout/"', count=1)
        self.assertNotContains(response, 'href="/admin/password_change/"')
        settings = self.client.get(reverse("admin:settings"))
        self.assertContains(settings, 'href="/admin/password_change/"')

    def test_category_list_excludes_parents_but_keeps_independent_categories(self):
        independent = Category.objects.create(name="Independent category")
        empty_parent = Category.objects.create(name="Empty parent", is_parent_category=True)
        response = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertEqual(set(response.context["cl"].result_list), {self.child, independent})
        self.assertEqual(response.context["cl"].full_result_count, 2)
        self.assertContains(response, 'class="category-count">2</span>')
        edit = self.client.get(reverse("admin:catalog_category_change", args=[empty_parent.pk]))
        self.assertEqual(edit.status_code, 200)
        self.assertNotContains(edit, 'id="id_parent"')
        # Both checked and unchecked indicators are disabled and have no field name.
        self.assertContains(response, 'disabled checked aria-label="Active"')
        self.assertContains(response, 'disabled  aria-label="Inactive"')
        form = response.context["cl"].formset.forms[0]
        self.assertNotIn("active_status", form.fields)

    def test_categories_follow_dashboard_and_settings_precede_account(self):
        response = self.client.get(reverse("admin:index"))
        sidebar = response.content.decode().split('<aside id="nav-sidebar"')[1].split("</aside>")[0]
        self.assertEqual(sidebar.count('href="/admin/catalog/category/"'), 1)
        self.assertLess(
            sidebar.index('href="/admin/catalog/category/"'),
            sidebar.index('href="/categories/"'),
        )
        self.assertLess(
            sidebar.index('href="/categories/"'),
            sidebar.index('href="/admin/settings/"'),
        )
        self.assertLess(
            sidebar.index('href="/admin/settings/"'),
            sidebar.index('<details class="retail-sidebar-account">'),
        )

    def test_category_overview_metrics_use_categories_only(self):
        Category.objects.create(name="Independent")
        Category.objects.create(name="Empty parent", is_parent_category=True)
        response = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertEqual(
            response.context["category_metrics"],
            {"total": 2, "active": 1, "inactive": 1, "independent": 1},
        )
        self.assertContains(response, 'aria-label="Category overview"')

    def test_parent_categories_page_and_headers(self):
        empty_parent = Category.objects.create(name="Empty parent", is_parent_category=True)
        Category.objects.create(name="Independent")
        url = reverse("admin:catalog_parent_categories")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["cl"].result_list), {self.parent, empty_parent})
        self.assertEqual(response.context["category_metrics"]["independent"], 1)
        self.assertContains(response, "Without categories")
        self.assertContains(response, "Add parent category")
        self.assertContains(response, "<strong>Parent Categories</strong>")
        self.assertNotContains(response, 'id="category-parent"')
        filtered = self.client.get(url, {"q": "Empty"})
        self.assertEqual(list(filtered.context["cl"].result_list), [empty_parent])
        for route, header in (
            ("catalog_category_changelist", "Categories"),
            ("settings", "Settings"),
        ):
            page = self.client.get(reverse("admin:" + route))
            self.assertContains(page, f"<strong>{header}</strong>")

    def test_delete_popup_is_available_on_both_lists_and_edit_page(self):
        for url in (
            reverse("admin:catalog_category_changelist"),
            reverse("admin:catalog_parent_categories"),
            reverse("admin:catalog_category_change", args=[self.child.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, '<dialog class="category-delete-dialog"', count=1)
                self.assertContains(response, "dialog.showModal()")
                self.assertContains(response, "form.action = link.href")
                self.assertContains(response, "cancelButton.addEventListener('click', close)")

    def test_reference_overview_preserves_live_data_and_account_controls(self):
        independent = Category.objects.create(name="Independent")
        Category.objects.create(name="Empty parent", is_parent_category=True)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Store overview")
        self.assertContains(response, "YOUR RETAIL WORKSPACE")
        self.assertContains(response, 'class="retail-kpi-icon"', count=4)
        self.assertContains(response, "Recent activity")
        self.assertContains(response, "Sign out")
        self.assertNotContains(response, "INTERACTIVE PROTOTYPE")
        self.assertNotContains(response, "Role preview")
        self.assertEqual(response.context["category_summary"]["total"], 2)
        self.assertEqual(response.context["parent_category_count"], 2)
        self.assertEqual(set(response.context["recent_categories"]), {independent, self.child})
