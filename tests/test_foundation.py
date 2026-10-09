import os
from unittest import TestCase
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from config.environment import configuration


class EnvironmentTests(TestCase):
    def setUp(self):
        self.env = {
            "DJANGO_SECRET_KEY": "synthetic-test-key-" * 4,
            "DJANGO_DEBUG": "false",
            "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,[::1]",
            "DB_NAME": "synthetic_dev",
            "DB_TEST_NAME": "test_synthetic",
            "DB_USER": "synthetic",
            "DB_PASSWORD": "synthetic-password",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432",
        }

    def test_valid_configuration_is_postgresql_only(self):
        result = configuration(self.env)
        self.assertFalse(result["DEBUG"])
        self.assertEqual(result["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")

    def test_secret_and_password_preserve_significant_whitespace(self):
        secret = "  " + self.env["DJANGO_SECRET_KEY"] + " \t"
        password = "  synthetic-password \t"
        result = configuration(self.env | {"DJANGO_SECRET_KEY": secret, "DB_PASSWORD": password})
        self.assertEqual(result["SECRET_KEY"], secret)
        self.assertEqual(result["DATABASES"]["default"]["PASSWORD"], password)

    def test_every_required_setting_rejects_missing_blank_and_placeholder(self):
        for name in self.env:
            for value in (None, " ", "replace-this"):
                with self.subTest(name=name, value=value):
                    env = self.env.copy()
                    if value is None:
                        del env[name]
                    else:
                        env[name] = value
                    with self.assertRaises(ImproperlyConfigured):
                        configuration(env)

    def test_invalid_values_do_not_echo_secrets(self):
        cases = {
            "DJANGO_SECRET_KEY": ["short-secret"],
            "DJANGO_DEBUG": ["yes", "1"],
            "DJANGO_ALLOWED_HOSTS": [
                "*",
                "localhost:8000",
                "https://localhost",
                "localhost,",
                "[127.0.0.1",
                "[127.0.0.1]",
                "::1",
                "[::1",
                "a..b",
                "-host",
                "host-",
            ],
            "DB_PORT": ["0", "65536", "abc", "3.5", "1" * 5000, "\uff11\uff12\uff13", "\u00b2"],
            "DB_NAME": ["postgres", "template0", "template1", "a" * 64, "caf\u00e9", "with-hyphen"],
            "DB_TEST_NAME": ["synthetic_dev", "other_database", "test_" + "a" * 59],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ImproperlyConfigured) as raised:
                        configuration(self.env | {name: value})
                    self.assertNotIn(self.env["DB_PASSWORD"], str(raised.exception))
                    self.assertNotIn(self.env["DJANGO_SECRET_KEY"], str(raised.exception))

    def test_postgresql_truncation_cannot_alias_test_and_development_names(self):
        shared_prefix = "test_" + "a" * 58
        with self.assertRaises(ImproperlyConfigured):
            configuration(
                self.env | {"DB_NAME": shared_prefix, "DB_TEST_NAME": shared_prefix + "b"}
            )


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class HealthTests(SimpleTestCase):
    def test_health_is_safe_liveness_without_database_queries(self):
        with patch(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
            side_effect=AssertionError("Health must not connect to a database"),
        ):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_head_and_disallowed_methods(self):
        self.assertEqual(self.client.head("/health/").status_code, 200)
        self.assertEqual(self.client.head("/health/").content, b"")
        for method in ("post", "put", "patch", "delete", "options"):
            self.assertEqual(getattr(self.client, method)("/health/").status_code, 405)

    def test_invalid_host_and_missing_routes_do_not_disclose_configuration(self):
        response = self.client.get("/health/", HTTP_HOST="untrusted.invalid")
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, settings.SECRET_KEY, status_code=400)
        for route in ("/", "/admin/", "/products/"):
            self.assertEqual(self.client.get(route).status_code, 404)


class PostgreSQLTests(TransactionTestCase):
    def test_real_postgresql_test_database_and_rollback(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
        self.assertEqual(database, os.environ["DB_TEST_NAME"])
        self.assertNotEqual(database, os.environ["DB_NAME"])
        with connection.cursor() as cursor:
            cursor.execute("CREATE TEMP TABLE foundation_probe (value integer)")
        try:
            with self.assertRaisesMessage(RuntimeError, "synthetic rollback"):
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("INSERT INTO foundation_probe VALUES (1)")
                    raise RuntimeError("synthetic rollback")
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM foundation_probe")
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE foundation_probe")
