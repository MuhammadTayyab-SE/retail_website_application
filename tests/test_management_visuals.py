from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from access.models import AuditEvent, Role, WorkerProfile
from catalog.models import Category


@override_settings(ALLOWED_HOSTS=["testserver"])
class ManagementScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            "owner", password="Synthetic-Password-123!"
        )
        cls.role = Role.objects.create(name="Category reader")
        cls.role.permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="view_category")
        )
        cls.worker = get_user_model().objects.create_user(
            "worker",
            first_name="Sample",
            last_name="Employee",
            email="worker@example.invalid",
            is_staff=True,
        )
        WorkerProfile.objects.create(user=cls.worker, role=cls.role)

    def setUp(self):
        self.client.force_login(self.owner)

    def test_team_reference_layout_and_role_status_search_filters(self):
        url = reverse("admin:auth_user_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Team &amp; access")
        self.assertContains(response, "Team members")
        self.assertContains(response, "Sample Employee")
        self.assertContains(response, "Super Admin")
        response = self.client.get(
            url,
            {
                "q": "Sample",
                "workerprofile__role__id__exact": self.role.pk,
                "is_active__exact": "1",
            },
        )
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertEqual(list(response.context["cl"].result_list), [self.worker])
        self.assertEqual(
            self.client.get(
                url, {"is_active__exact": "", "workerprofile__role__id__exact": ""}
            ).status_code,
            200,
        )

    def test_role_and_activity_screens_use_shared_layout_and_date_filters(self):
        response = self.client.get(reverse("admin:access_role_changelist"))
        self.assertContains(response, "Access roles")
        self.assertContains(response, "Can view category")
        event = AuditEvent.objects.create(
            actor_name="worker", action="view", module="catalog.category", target_id="12"
        )
        response = self.client.get(
            reverse("admin:access_auditevent_changelist"),
            {
                "actor_name": "worker",
                "outcome": "success",
                "module": "catalog.category",
                "occurred_at__date__gte": event.occurred_at.date().isoformat(),
                "occurred_at__date__lte": event.occurred_at.date().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertContains(response, "Record #12")
        self.assertContains(response, "Date &amp; time (UTC)")

    def test_management_forms_and_sidebar_order(self):
        for url in [
            reverse("admin:auth_user_add"),
            reverse("admin:auth_user_change", args=[self.owner.pk]),
            reverse("admin:access_role_add"),
        ]:
            response = self.client.get(url)
            self.assertContains(response, "management-form-grid")
        role_page = self.client.get(reverse("admin:access_role_add"))
        self.assertContains(role_page, 'class="permission-grid"')
        html = self.client.get(reverse("admin:index")).content.decode()
        parent = html.index('href="/admin/catalog/category/parents/"')
        catalog = html.index('href="/categories/"', parent)
        workers = html.index('href="/admin/auth/user/"', parent)
        self.assertLess(parent, catalog)
        self.assertLess(catalog, workers)
        self.assertIn("Parent Categories</a>", html)

    def test_final_active_super_admin_cannot_be_deactivated(self):
        response = self.client.post(
            reverse("admin:auth_user_change", args=[self.owner.pk]),
            {
                "username": "owner",
                "first_name": "",
                "last_name": "",
                "email": "",
                "role": "",
            },
        )
        self.assertContains(response, "Keep at least one active Super Admin.")
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_explicit_catalog_assignment_preserves_unknown_creation_time_and_is_idempotent(self):
        legacy = Category.objects.create(name="Legacy parent", is_parent_category=True)
        child = Category.objects.create(name="Legacy child", parent=legacy)
        Category.objects.filter(pk__in=[legacy.pk, child.pk]).update(created_at=None)
        call_command("assign_catalog_owner", "worker", stdout=StringIO())
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.is_superuser)
        self.assertTrue(self.worker.is_staff)
        for category in Category.objects.all():
            self.assertEqual(category.created_by, self.worker)
            self.assertEqual(category.updated_by, self.worker)
            self.assertIsNone(category.created_at)
            self.assertIsNotNone(category.updated_at)
        self.assertEqual(AuditEvent.objects.filter(action="attribution_assignment").count(), 2)
        call_command("assign_catalog_owner", "worker", stdout=StringIO())
        self.assertEqual(AuditEvent.objects.filter(action="attribution_assignment").count(), 2)
