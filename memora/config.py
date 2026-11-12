"""Explicit application-scoped runtime configuration; no ambient credentials."""

import json
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str = "127.0.0.1"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = "babar_memory"
    user: str = "babar_memory"
    password: SecretStr
    namespace: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    revision: str = Field(
        default="c9745ed1d9f207416be6d2e6f8de32d1f16199bf", pattern=r"^[0-9a-f]{40}$"
    )
    dimension: int = Field(default=384, ge=1, le=2000)

    sslmode: (
        Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        | None
    ) = None
    sslrootcert: str | None = None
    sslcert: str | None = None
    sslkey: str | None = None
    connect_timeout: int = Field(default=5, ge=1, le=60)

    @model_validator(mode="after")
    def transport_policy(self):
        if self.host not in ("127.0.0.1", "localhost", "::1") and self.sslmode is None:
            raise ValueError("Non-loopback PostgreSQL requires an explicit sslmode.")
        return self

    def connection(self):
        return dict(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password.get_secret_value(),
            connect_timeout=self.connect_timeout,
            **{
                key: getattr(self, key)
                for key in ("sslmode", "sslrootcert", "sslcert", "sslkey")
                if getattr(self, key) is not None
            },
        )

    @property
    def identity(self):
        return {
            "model": self.model,
            "revision": self.revision,
            "dimension": self.dimension,
        }


def load_config():
    path = Path(os.environ["MEMORA_CONFIG"]).expanduser().resolve()
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & (
        stat.S_IRWXG | stat.S_IRWXO
    ):
        raise ValueError(
            "Memora configuration must have owner-only permissions (chmod 600)."
        )
    config = Config.model_validate(json.loads(path.read_text()))
    config.connection()
    return config


def admin_parameters(database, environment=None):
    """Validate operator transport settings without inheriting runtime credentials."""
    environment = os.environ if environment is None else environment
    profile = Config(
        host=environment.get("PGHOST", "127.0.0.1"),
        port=int(environment.get("PGPORT", "5432")),
        database=database,
        user=environment.get("PGUSER") or "",
        password=environment.get("PGPASSWORD") or "",
        namespace="administrator",
        connect_timeout=int(environment.get("PGCONNECT_TIMEOUT", "5")),
        **{
            name: environment["PG" + name.upper()]
            for name in ("sslmode", "sslrootcert", "sslcert", "sslkey")
            if "PG" + name.upper() in environment
        },
    )
    parameters = profile.connection()
    # Preserve libpq's OS-user/password-file defaults for native maintenance.
    for name, variable in (("user", "PGUSER"), ("password", "PGPASSWORD")):
        if variable not in environment:
            parameters.pop(name)
    return parameters
