"""Validate explicit environment configuration without exposing its values."""

import ipaddress
import re
from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value or value.startswith("replace-"):
        raise ImproperlyConfigured(f"{name} must be configured with a non-placeholder value.")
    return value


def configuration(env: Mapping[str, str]) -> dict:
    secret = required(env, "DJANGO_SECRET_KEY")
    if len(secret) < 50:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters.")
    debug = required(env, "DJANGO_DEBUG").lower()
    if debug not in {"true", "false"}:
        raise ImproperlyConfigured("DJANGO_DEBUG must be true or false.")
    hosts = [host.strip() for host in required(env, "DJANGO_ALLOWED_HOSTS").split(",")]
    for host in hosts:
        if host.startswith("[") and host.endswith("]"):
            try:
                valid = isinstance(ipaddress.ip_address(host[1:-1]), ipaddress.IPv6Address)
            except ValueError:
                valid = False
        else:
            valid = len(host) <= 253 and all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in host.split(".")
            )
        if not valid:
            raise ImproperlyConfigured(
                "DJANGO_ALLOWED_HOSTS must list explicit hosts without ports."
            )
    port = required(env, "DB_PORT")
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise ImproperlyConfigured("DB_PORT must be an integer between 1 and 65535.")
    name = required(env, "DB_NAME")
    test_name = required(env, "DB_TEST_NAME")
    for setting, value in (("DB_NAME", name), ("DB_TEST_NAME", test_name)):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value) or value in {
            "postgres",
            "template0",
            "template1",
        }:
            raise ImproperlyConfigured(
                f"{setting} must be a non-system ASCII database name of at most 63 characters."
            )
    if test_name == name or not test_name.startswith("test_"):
        raise ImproperlyConfigured("DB_TEST_NAME must start with test_ and differ from DB_NAME.")
    database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": required(env, "DB_USER"),
        "PASSWORD": required(env, "DB_PASSWORD"),
        "HOST": required(env, "DB_HOST"),
        "PORT": int(port),
        "TEST": {"NAME": test_name},
        "OPTIONS": {"connect_timeout": 5},
    }
    return {
        "SECRET_KEY": secret,
        "DEBUG": debug == "true",
        "ALLOWED_HOSTS": hosts,
        "DATABASES": {"default": database},
    }
