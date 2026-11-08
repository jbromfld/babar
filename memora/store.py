"""Parameterized, namespace-bound persistence. Similarity never authorizes a write."""

import math
import re
from contextlib import contextmanager
from datetime import date
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=400)
    kind: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    source_date: date
    source_excerpt: str = Field(default="", max_length=1000)
    cues: list[str] = Field(default_factory=list, max_length=8)
    status: str = Field(default="active", pattern=r"^(active|completed|abandoned)$")

    @field_validator("cues")
    @classmethod
    def validate_cues(cls, values):
        if any(not value.strip() or len(value) > 50 for value in values):
            raise ValueError("Cues must contain 1–50 characters.")
        return sorted(set(value.strip().casefold() for value in values))


class StoreError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def vector(values, dimension):
    if (
        len(values) != dimension
        or any(not math.isfinite(v) for v in values)
        or not any(values)
    ):
        raise ValueError("Invalid embedding.")
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def public(row):
    return {
        "id": str(row["id"]),
        "revision": row["revision"],
        **row["memory_value"],
        "title": row["primary_abstraction"],
        "cues": row["cue_anchors"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


class Store:
    def __init__(self, config, embed):
        self.config, self.embed = config, embed

    @contextmanager
    def connect(self):
        conn = psycopg2.connect(
            **self.config.connection(), cursor_factory=RealDictCursor
        )
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SET statement_timeout = '5000ms'")
                    cur.execute(
                        "SELECT identity, (SELECT max(version) FROM memora_migrations) AS version, (SELECT atttypmod FROM pg_attribute WHERE attrelid='public.memora_notes'::regclass AND attname='primary_embedding') AS dimension FROM memora_model WHERE singleton"
                    )
                    row = cur.fetchone()
                    if (
                        not row
                        or row["identity"] != self.config.identity
                        or row["version"] != 1
                        or row["dimension"] != self.config.dimension
                    ):
                        raise StoreError(
                            "configuration",
                            "Embedding identity changed; run an explicit reindex.",
                        )
                yield conn
        finally:
            conn.close()

    def status(self):
        # Also prove offline weights are present before reporting ready.
        self.embedding("memory readiness")
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS count FROM memora_notes WHERE namespace=%s",
                (self.config.namespace,),
            )
            return {"ready": True, "count": cur.fetchone()["count"]}

    def embedding(self, text):
        return vector(self.embed(text), self.config.dimension)

    def list(self, offset=0, limit=25):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 50:
            raise StoreError("invalid", "Invalid pagination.")
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM memora_notes WHERE namespace=%s ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                (self.config.namespace, limit + 1, offset),
            )
            rows = cur.fetchall()
        return {
            "items": [public(row) for row in rows[:limit]],
            "next_offset": offset + limit if len(rows) > limit else None,
        }

    def get(self, id):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM memora_notes WHERE namespace=%s AND id=%s",
                (self.config.namespace, str(UUID(str(id)))),
            )
            row = cur.fetchone()
            if row is None:
                raise StoreError("not_found", "Memory not found.")
            cur.execute(
                "SELECT document FROM memora_revisions WHERE namespace=%s AND note_id=%s ORDER BY revision DESC",
                (self.config.namespace, str(id)),
            )
            return {**public(row), "history": [r["document"] for r in cur.fetchall()]}

    def search(self, query, limit=3):
        if not query.strip() or len(query) > 2000 or not 1 <= limit <= 10:
            raise StoreError(
                "invalid", "Search requires 1–2000 characters and a limit of 1–10."
            )
        embedding = self.embedding(query)
        terms = sorted(set(re.findall(r"[a-z0-9]{3,}", query.casefold())))[:40]
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT *, 1-(primary_embedding <=> %s::vector) AS similarity,
              ts_rank_cd(to_tsvector('english',primary_abstraction || ' ' || (memory_value->>'text') || ' ' || array_to_string(cue_anchors,' ')),
                         to_tsquery('english',%s)) AS lexical,
              (cue_anchors && %s::text[]) AS cue_match
              FROM memora_notes WHERE namespace=%s AND status='active'
              ORDER BY primary_embedding <=> %s::vector, id LIMIT 100""",
                (embedding, " | ".join(terms), terms, self.config.namespace, embedding),
            )
            rows = cur.fetchall()
        eligible = [
            r
            for r in rows
            if r["similarity"] >= 0.42 or r["lexical"] > 0 or r["cue_match"]
        ]
        eligible.sort(
            key=lambda r: (
                -(
                    r["similarity"]
                    + min(float(r["lexical"]), 0.25)
                    + 0.1 * r["cue_match"]
                ),
                str(r["id"]),
            )
        )
        return {"items": [public(r) for r in eligible[:limit]]}

    def create(self, note, create_key):
        note = Note.model_validate(note)
        key = str(UUID(str(create_key)))
        embedding = self.embedding(
            note.title + " " + note.text + " " + " ".join(note.cues)
        )
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (self.config.namespace + key,),
            )
            cur.execute(
                "SELECT * FROM memora_notes WHERE namespace=%s AND create_key=%s",
                (self.config.namespace, key),
            )
            existing = cur.fetchone()
            if existing:
                saved = {k: public(existing)[k] for k in Note.model_fields}
                if saved != note.model_dump(mode="json"):
                    raise StoreError(
                        "conflict",
                        "This save key was already used for different content.",
                    )
                return public(existing)
            cur.execute(
                """INSERT INTO memora_notes(namespace,id,create_key,primary_abstraction,primary_embedding,memory_value,cue_anchors,revision,status)
              VALUES(%s,%s,%s,%s,%s::vector,%s,%s,1,%s) RETURNING *""",
                (
                    self.config.namespace,
                    str(uuid4()),
                    key,
                    note.title,
                    embedding,
                    Json(note.model_dump(mode="json")),
                    note.cues,
                    note.status,
                ),
            )
            row = public(cur.fetchone())
            self._revision(cur, row)
            return row

    def _revision(self, cur, row):
        cur.execute(
            "INSERT INTO memora_revisions(namespace,note_id,revision,document) VALUES(%s,%s,%s,%s)",
            (self.config.namespace, row["id"], row["revision"], Json(row)),
        )

    def update(self, id, note, expected_revision):
        note = Note.model_validate(note)
        embedding = self.embedding(
            note.title + " " + note.text + " " + " ".join(note.cues)
        )
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE memora_notes SET primary_abstraction=%s,primary_embedding=%s::vector,
              memory_value=%s,cue_anchors=%s,status=%s,revision=revision+1,updated_at=now()
              WHERE namespace=%s AND id=%s AND revision=%s RETURNING *""",
                (
                    note.title,
                    embedding,
                    Json(note.model_dump(mode="json")),
                    note.cues,
                    note.status,
                    self.config.namespace,
                    str(UUID(str(id))),
                    expected_revision,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise StoreError(
                    "conflict", "Memory changed or was forgotten. Reload before saving."
                )
            result = public(row)
            self._revision(cur, result)
            return result

    def forget(self, id, expected_revision):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM memora_notes WHERE namespace=%s AND id=%s AND revision=%s RETURNING id",
                (self.config.namespace, str(UUID(str(id))), expected_revision),
            )
            if cur.fetchone() is None:
                raise StoreError(
                    "conflict", "Memory changed or was already forgotten. Reload first."
                )
        return {"forgotten": True}
