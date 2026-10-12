from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from manage import load_local_environment


class LocalEnvironmentTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / ".env"

    def test_literal_values_quotes_bom_and_process_precedence(self):
        self.path.write_text(
            "\ufeff# local settings\n\n"
            "DJANGO_SECRET_KEY='  synthetic-secret  '\n"
            'DB_PASSWORD="literal=$HOME#value"\n'
            "DJANGO_DEBUG=true\n",
            encoding="utf-8",
        )
        env = {"DJANGO_DEBUG": "false"}
        load_local_environment(self.path, env)
        self.assertEqual(env["DJANGO_SECRET_KEY"], "  synthetic-secret  ")
        self.assertEqual(env["DB_PASSWORD"], "literal=$HOME#value")
        self.assertEqual(env["DJANGO_DEBUG"], "false")

    def test_missing_file_allows_environment_only_launch(self):
        env = {"DJANGO_DEBUG": "false"}
        load_local_environment(self.path, env)
        self.assertEqual(env, {"DJANGO_DEBUG": "false"})

    def test_invalid_file_does_not_echo_values_or_partially_load(self):
        for invalid in ("invalid-key=private-value", 'DB_PASSWORD="private-value'):
            with self.subTest(invalid=invalid):
                self.path.write_text("DJANGO_DEBUG=true\n" + invalid, encoding="utf-8")
                env = {}
                with self.assertRaises(ValueError) as raised:
                    load_local_environment(self.path, env)
                self.assertNotIn("private-value", str(raised.exception))
                self.assertEqual(env, {})
