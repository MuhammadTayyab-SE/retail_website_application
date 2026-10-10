from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from access.models import AuditEvent, Role, WorkerProfile
from catalog.models import Category


@override_settings(ALLOWED_HOSTS=["testserver"])
class RolesAndAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Synthetic-Worker-Password-831!"
        cls.owner = get_user_model().objects.create_superuser("owner", password=cls.password)
        cls.editor_role = Role.objects.create(name="Category editor")
        cls.reader_role = Role.objects.create(name="Parent reader")
        cls.editor_role.permissions.set(
            Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=[
                    "view_category",
                    "add_category",
                    "change_category",
                    "delete_category",
                ],
            )
        )
        cls.reader_role.permissions.set(
            Permission.objects.filter(
                content_type__app_label="catalog",
                codename="view_parentcategory",
            )
        )
        cls.editor = get_user_model().objects.create_user(
            "editor", password=cls.password, is_staff=True
        )
        cls.reader = get_user_model().objects.create_user(
            "reader", password=cls.password, is_staff=True
        )
        cls.unassigned = get_user_model().objects.create_user(
            "unassigned", password=cls.password, is_staff=True
        )
        WorkerProfile.objects.create(user=cls.editor, role=cls.editor_role)
        WorkerProfile.objects.create(user=cls.reader, role=cls.reader_role)
        cls.parent = Category.objects.create(name="Parent", is_parent_category=True)
        cls.child = Category.objects.create(name="Child", parent=cls.parent)

    def sign_in(self, user):
        self.client.force_login(user)

    def category_data(self, **kwargs):
        return {
            "name": "New category",
            "position": "1",
            "is_active": "on",
            "photo_x": "50",
            "photo_y": "50",
            "photo_zoom": "100",
            **kwargs,
        }

    def test_two_roles_login_and_distinct_modules(self):
        for user in [self.editor, self.reader]:
            self.client.logout()
            response = self.client.post(
                reverse("admin:login"),
                {
                    "username": user.username,
                    "password": self.password,
                },
            )
            self.assertRedirects(response, reverse("admin:index"))
        self.sign_in(self.editor)
        self.assertEqual(
            self.client.get(reverse("admin:catalog_category_changelist")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("admin:catalog_parent_categories")).status_code, 403
        )
        self.assertNotContains(
            self.client.get(reverse("admin:index")), 'href="/admin/access/role/"'
        )
        self.sign_in(self.reader)
        self.assertEqual(
            self.client.get(reverse("admin:catalog_parent_categories")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("admin:catalog_category_changelist")).status_code, 403
        )

    def test_direct_objects_and_photo_urls_obey_module_permission(self):
        self.sign_in(self.editor)
        self.assertEqual(
            self.client.get(
                reverse("admin:catalog_category_change", args=[self.parent.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("category-photo", args=[self.parent.pk])).status_code, 403
        )
        self.sign_in(self.reader)
        self.assertEqual(
            self.client.get(
                reverse("admin:catalog_category_change", args=[self.child.pk])
            ).status_code,
            403,
        )

    def test_read_only_role_cannot_mutate_parent_or_child(self):
        self.sign_in(self.reader)
        urls = [
            reverse("admin:catalog_category_add") + "?kind=parent",
            reverse("admin:catalog_category_change", args=[self.parent.pk]),
            reverse("admin:catalog_category_delete", args=[self.parent.pk]),
            reverse("admin:catalog_category_change", args=[self.child.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.post(url, self.category_data(post="yes")).status_code, 403)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.name, "Parent")
        response = self.client.get(reverse("admin:catalog_parent_categories"))
        self.assertNotContains(response, 'class="category-delete-link"')
        self.assertNotContains(response, 'name="form-0-position"')

    def test_active_session_reacts_to_permission_and_account_changes(self):
        self.sign_in(self.editor)
        url = reverse("admin:catalog_category_changelist")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.editor_role.permissions.clear()
        self.assertEqual(self.client.get(url).status_code, 403)
        WorkerProfile.objects.filter(user=self.editor).update(role=self.reader_role)
        self.assertEqual(
            self.client.get(reverse("admin:catalog_parent_categories")).status_code, 200
        )
        get_user_model().objects.filter(pk=self.editor.pk).update(is_active=False)
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_unassigned_and_inactive_workers_cannot_login(self):
        self.reader.is_active = False
        self.reader.save()
        for user in [self.unassigned, self.reader]:
            self.client.post(
                reverse("admin:login"), {"username": user.username, "password": self.password}
            )
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertGreaterEqual(
            AuditEvent.objects.filter(action="login", outcome="failed").count(), 2
        )

    def test_worker_cannot_administer_accounts_roles_audit_or_passwords(self):
        # Even accidentally stored management grants cannot bypass the hard boundary.
        self.editor_role.permissions.add(
            *Permission.objects.exclude(content_type__app_label="catalog")
        )
        self.sign_in(self.editor)
        urls = [
            reverse("admin:auth_user_changelist"),
            reverse("admin:auth_user_add"),
            reverse("admin:auth_user_change", args=[self.owner.pk]),
            reverse("admin:auth_user_password_change", args=[self.owner.pk]),
            reverse("admin:access_role_changelist"),
            reverse("admin:access_role_add"),
            reverse("admin:access_auditevent_changelist"),
        ]
        for url in urls:
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url).status_code, 403, url)

    def test_super_admin_creates_worker_assigns_role_and_resets_password(self):
        self.sign_in(self.owner)
        self.assertEqual(self.client.get(reverse("admin:auth_user_add")).status_code, 200)
        response = self.client.post(
            reverse("admin:auth_user_add"),
            {
                "username": "new-worker",
                "first_name": "New",
                "last_name": "Worker",
                "email": "worker@example.invalid",
                "is_active": "on",
                "role": self.editor_role.pk,
                "password1": self.password,
                "password2": self.password,
                "usable_password": "true",
            },
        )
        self.assertEqual(
            response.status_code, 302, response.context and response.context.get("errors")
        )
        worker = get_user_model().objects.get(username="new-worker")
        self.assertTrue(worker.is_staff)
        self.assertFalse(worker.is_superuser)
        self.assertEqual(worker.workerprofile.role, self.editor_role)
        page = self.client.get(reverse("admin:auth_user_change", args=[worker.pk]))
        self.assertNotContains(page, worker.password)
        new_password = "Reset-Synthetic-Password-938!"
        response = self.client.post(
            reverse("admin:auth_user_password_change", args=[worker.pk]),
            {
                "password1": new_password,
                "password2": new_password,
                "usable_password": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        worker.refresh_from_db()
        self.assertTrue(worker.check_password(new_password))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="password_reset", target_id=str(worker.pk), actor_id=self.owner.pk
            ).exists()
        )
        for event in AuditEvent.objects.all():
            self.assertNotIn(new_password, str(event.details))
            self.assertNotIn(worker.password, str(event.details))

    def test_worker_can_change_only_own_password(self):
        self.sign_in(self.editor)
        response = self.client.post(
            reverse("admin:password_change"),
            {
                "old_password": self.password,
                "new_password1": "Own-New-Password-123!",
                "new_password2": "Own-New-Password-123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.editor.refresh_from_db()
        self.assertTrue(self.editor.check_password("Own-New-Password-123!"))
        self.assertTrue(
            AuditEvent.objects.filter(action="password_change", actor_id=self.editor.pk).exists()
        )

    def test_role_form_excludes_and_rejects_management_permissions(self):
        self.sign_in(self.owner)
        forbidden = Permission.objects.get(content_type__app_label="auth", codename="change_user")
        response = self.client.post(
            reverse("admin:access_role_add"),
            {
                "name": "Escalated role",
                "permissions": [forbidden.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Role.objects.filter(name="Escalated role").exists())
        permitted = Permission.objects.get(
            content_type__app_label="catalog", codename="view_category"
        )
        response = self.client.post(
            reverse("admin:access_role_add"),
            {
                "name": "New reader",
                "permissions": [permitted.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditEvent.objects.filter(action="permissions_change", actor_id=self.owner.pk).exists()
        )

    def test_parent_and_category_attribution_cannot_be_forged(self):
        self.sign_in(self.owner)
        for name, suffix in [("New parent", "?kind=parent"), ("Independent", "")]:
            response = self.client.post(
                reverse("admin:catalog_category_add") + suffix,
                self.category_data(name=name, created_by=self.editor.pk, updated_by=self.editor.pk),
            )
            self.assertEqual(response.status_code, 302)
            obj = Category.objects.get(name=name)
            self.assertEqual(obj.created_by, self.owner)
            self.assertEqual(obj.updated_by, self.owner)
            self.assertIsNotNone(obj.created_at)
            self.assertIsNotNone(obj.updated_at)
        obj = Category.objects.get(name="Independent")
        created_at = obj.created_at
        self.sign_in(self.editor)
        response = self.client.post(
            reverse("admin:catalog_category_change", args=[obj.pk]),
            self.category_data(name="Edited", created_by=self.editor.pk),
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.created_by, self.owner)
        self.assertEqual(obj.created_at, created_at)
        self.assertEqual(obj.updated_by, self.editor)
        self.assertGreater(obj.updated_at, created_at)
        self.assertContains(
            self.client.get(reverse("admin:catalog_category_change", args=[obj.pk])),
            "Record history",
        )

    def test_legacy_attribution_remains_unknown_after_edit(self):
        Category.objects.filter(pk=self.child.pk).update(created_at=None)
        self.sign_in(self.owner)
        self.client.post(
            reverse("admin:catalog_category_change", args=[self.child.pk]),
            self.category_data(name="Child", parent=self.parent.pk),
        )
        self.child.refresh_from_db()
        self.assertIsNone(self.child.created_by)
        self.assertIsNone(self.child.created_at)
        self.assertEqual(self.child.updated_by, self.owner)

    def test_bulk_position_save_has_attribution_and_audit(self):
        self.sign_in(self.editor)
        response = self.client.post(
            reverse("admin:catalog_category_changelist"),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": self.child.pk,
                "form-0-position": "7",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.position, 7)
        self.assertEqual(self.child.updated_by, self.editor)
        self.assertTrue(
            AuditEvent.objects.filter(
                module="catalog.category", action="update", actor_id=self.editor.pk
            ).exists()
        )

    def test_parent_delete_requires_descendant_permission_and_logs_cascade(self):
        self.reader_role.permissions.add(
            Permission.objects.get(
                content_type__app_label="catalog", codename="delete_parentcategory"
            )
        )
        self.sign_in(self.reader)
        url = reverse("admin:catalog_category_delete", args=[self.parent.pk])
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        self.assertTrue(Category.objects.filter(pk=self.child.pk).exists())
        self.sign_in(self.owner)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assertFalse(Category.objects.filter(pk=self.child.pk).exists())
        self.assertEqual(
            AuditEvent.objects.filter(module="catalog.category", action="delete").count(), 2
        )

    def test_audit_is_immutable_and_survives_target_deletion(self):
        self.sign_in(self.owner)
        self.client.get(reverse("admin:index"))
        event = AuditEvent.objects.first()
        for url in [
            reverse("admin:access_auditevent_add"),
            reverse("admin:access_auditevent_change", args=[event.pk]),
            reverse("admin:access_auditevent_delete", args=[event.pk]),
        ]:
            self.assertEqual(self.client.post(url, {"action": "forged"}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            event.delete()
        with self.assertRaises(PermissionDenied):
            event.save()
        with self.assertRaises(PermissionDenied):
            AuditEvent.objects.filter(pk=event.pk).update(action="forged")
        with self.assertRaises(PermissionDenied):
            AuditEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(PermissionDenied):
            AuditEvent(pk=event.pk, action="forged", module="portal").save()
        self.assertEqual(
            self.client.get(
                reverse("admin:access_auditevent_changelist") + "?actor_name=owner"
            ).status_code,
            200,
        )

    def test_authorship_protects_employee_deletion(self):
        Category.objects.create(name="Attributed", created_by=self.editor)
        with self.assertRaises(ProtectedError):
            self.editor.delete()

    def test_reassignment_deactivation_and_password_reset_are_owner_controlled(self):
        self.sign_in(self.owner)
        response = self.client.post(
            reverse("admin:auth_user_change", args=[self.editor.pk]),
            {
                "username": self.editor.username,
                "first_name": "",
                "last_name": "",
                "email": "",
                "is_active": "on",
                "role": self.reader_role.pk,
                "is_superuser": "on",
                "user_permissions": [1],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.editor.refresh_from_db()
        self.assertFalse(self.editor.is_superuser)
        self.assertEqual(self.editor.workerprofile.role, self.reader_role)
        self.assertTrue(
            AuditEvent.objects.filter(module="access.workerprofile", action="update").exists()
        )
        response = self.client.post(
            reverse("admin:auth_user_change", args=[self.editor.pk]),
            {
                "username": self.editor.username,
                "first_name": "",
                "last_name": "",
                "email": "",
                "role": self.reader_role.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.editor.refresh_from_db()
        self.assertFalse(self.editor.is_active)

    def test_audit_actor_snapshot_survives_unattributed_employee_deletion(self):
        event = AuditEvent.objects.create(
            actor_id=self.unassigned.pk, actor_name="unassigned", action="view", module="portal"
        )
        self.unassigned.delete()
        event.refresh_from_db()
        self.assertEqual(event.actor_name, "unassigned")

    def test_add_only_role_can_create_without_read_or_update_access(self):
        self.editor_role.permissions.set(
            Permission.objects.filter(content_type__app_label="catalog", codename="add_category")
        )
        self.sign_in(self.editor)
        response = self.client.post(reverse("admin:catalog_category_add"), self.category_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Category.objects.filter(name="New category", created_by=self.editor).exists()
        )
        self.assertEqual(
            self.client.get(reverse("admin:catalog_category_changelist")).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:catalog_category_add") + "?kind=parent", self.category_data()
            ).status_code,
            403,
        )

    def test_parent_only_editor_can_bulk_update_parent_positions(self):
        self.reader_role.permissions.add(
            Permission.objects.get(
                content_type__app_label="catalog", codename="change_parentcategory"
            )
        )
        self.sign_in(self.reader)
        response = self.client.post(
            reverse("admin:catalog_parent_categories"),
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": self.parent.pk,
                "form-0-position": "9",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.position, 9)
        self.assertEqual(self.parent.updated_by, self.reader)

    def test_view_event_includes_target_id_and_authenticated_catalog_visit(self):
        self.sign_in(self.owner)
        self.client.get(reverse("admin:catalog_category_change", args=[self.child.pk]))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="view", target_id=str(self.child.pk), module="catalog.category"
            ).exists()
        )
        self.client.get(reverse("category-list"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="view", details__route="category-list", actor_id=self.owner.pk
            ).exists()
        )

    def test_assigned_role_cannot_be_deleted_and_failed_attempt_is_logged(self):
        self.sign_in(self.owner)
        response = self.client.post(
            reverse("admin:access_role_delete", args=[self.reader_role.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Role.objects.filter(pk=self.reader_role.pk).exists())
        event = AuditEvent.objects.filter(action="request", module="access.role").first()
        self.assertEqual(event.outcome, "failed")

    def test_views_denials_and_failed_forms_are_logged_without_request_secrets(self):
        self.sign_in(self.reader)
        self.client.get(reverse("admin:catalog_parent_categories"))
        self.client.post(
            reverse("admin:catalog_category_add"), {"password": "Never-log-this", "token": "secret"}
        )
        self.assertTrue(AuditEvent.objects.filter(action="view", actor_id=self.reader.pk).exists())
        self.assertTrue(
            AuditEvent.objects.filter(outcome="denied", actor_id=self.reader.pk).exists()
        )
        self.assertNotIn("Never-log-this", str(list(AuditEvent.objects.values("details"))))
        self.sign_in(self.owner)
        self.client.post(reverse("admin:catalog_category_add"), self.category_data(name=""))
        self.assertEqual(AuditEvent.objects.filter(action="request").first().outcome, "failed")
