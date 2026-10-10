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
        self.assertEqual(
            response.context["category_summary"],
            {"total": 2, "active": 1, "inactive": 1, "roots": 1},
        )
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
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/base_site.html")
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
