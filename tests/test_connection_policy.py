"""Connection policy checks do not require a database or model cache."""

import pytest

from memora.config import Config, admin_parameters


def test_legacy_profile():
    assert (
        Config(namespace="test", password="secret").connection()["connect_timeout"] == 5
    )


def test_remote_requires_explicit_transport():
    with pytest.raises(ValueError):
        Config(namespace="test", password="secret", host="db.example")


def test_remote_tls_parameters():
    config = Config(
        namespace="test",
        password="secret",
        host="db.example",
        sslmode="verify-full",
        sslrootcert="/trust/ca.pem",
        connect_timeout=9,
    )
    parameters = config.connection()
    assert parameters["sslmode"] == "verify-full"
    assert parameters["sslrootcert"] == "/trust/ca.pem"
    assert parameters["host"] == "db.example"
    assert parameters["connect_timeout"] == 9


@pytest.mark.parametrize("timeout", [0, 61])
def test_bounded_timeout(timeout):
    with pytest.raises(ValueError):
        Config(namespace="test", password="secret", connect_timeout=timeout)


def test_administrator_transport_is_independent():
    parameters = admin_parameters(
        "maintenance",
        {
            "PGHOST": "db.example",
            "PGSSLMODE": "verify-full",
            "PGUSER": "admin",
            "PGPASSWORD": "private",
            "PGSSLROOTCERT": "/trust/ca.pem",
            "PGCONNECT_TIMEOUT": "8",
        },
    )
    assert parameters["dbname"] == "maintenance"
    assert parameters["user"] == "admin"
    assert parameters["sslmode"] == "verify-full"
    assert parameters["connect_timeout"] == 8


def test_admin_remote_requires_tls_choice():
    with pytest.raises(ValueError):
        admin_parameters("maintenance", {"PGHOST": "db.example"})
