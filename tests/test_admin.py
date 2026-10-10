from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from config.admin import RetailAdminAuthenticationForm, site


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminPolicyTests(TestCase):
    def test_anonymous_admin_redirect_and_login_form(self):
        self.assertRedirects(
            self.client.get(reverse("admin:index")),
            reverse("admin:login") + "?next=" + reverse("admin:index"),
        )
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="password"')

    def test_custom_login_keeps_validation_and_redirect_target(self):
        target = reverse("admin:catalog_category_changelist")
        response = self.client.post(
            reverse("admin:login"),
            {"username": "<owner>", "password": "", "next": target},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "retail_admin/login.html")
        self.assertContains(response, "This field is required.")
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'value="&lt;owner&gt;"')
        self.assertContains(response, f'name="next" value="{target}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_only_active_staff_superusers_pass_the_site_gate(self):
        from itertools import product
        from types import SimpleNamespace

        for active, staff, superuser in product((False, True), repeat=3):
            user = get_user_model()(is_active=active, is_staff=staff, is_superuser=superuser)
            self.assertEqual(
                site.has_permission(SimpleNamespace(user=user)), active and staff and superuser
            )

    def test_staff_without_superuser_rejected_with_formatted_error(self):
        user = get_user_model()(is_active=True, is_staff=True, is_superuser=False)
        with self.assertRaises(ValidationError) as raised:
            RetailAdminAuthenticationForm().confirm_login_allowed(user)
        self.assertNotIn("%(username)s", str(raised.exception))


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "synthetic-admin-password-831!"
        cls.admin = get_user_model().objects.create_superuser(
            "owner", "owner@example.invalid", cls.password
        )
        cls.customer = get_user_model().objects.create_user("customer", password=cls.password)
        cls.staff = get_user_model().objects.create_user(
            "staff", password=cls.password, is_staff=True
        )
        cls.inactive = get_user_model().objects.create_superuser(
            "inactive", "inactive@example.invalid", cls.password, is_active=False
        )

    def test_owner_login_and_post_logout(self):
        response = self.client.post(
            reverse("admin:login"), {"username": "owner", "password": self.password}
        )
        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("admin:logout")).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_invalid_inactive_and_non_admin_login_denied(self):
        for username in ("customer", "staff", "inactive", "missing"):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse("admin:login"), {"username": username, "password": self.password}
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(
            reverse("admin:login"), {"username": "owner", "password": "incorrect"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_direct_admin_urls_reject_anonymous_and_non_admin_sessions(self):
        urls = [
            reverse("admin:index"),
            reverse("admin:catalog_category_changelist"),
            reverse("admin:catalog_category_add"),
            reverse("admin:settings"),
            reverse("admin:catalog_parent_categories"),
        ]
        for user in (None, self.customer, self.staff, self.inactive):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.get(url).status_code, 302)
                    self.assertEqual(self.client.post(url, {"name": "Forbidden"}).status_code, 302)

    def test_login_and_logout_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("admin:login"), {}).status_code, 403)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse("admin:logout")).status_code, 403)
