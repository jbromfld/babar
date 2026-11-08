"""Explicit application-scoped runtime configuration; no ambient credentials."""

import json
import os
import stat
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr


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

    def connection(self):
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Memora requires a loopback PostgreSQL host.")
        return dict(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password.get_secret_value(),
            connect_timeout=5,
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
