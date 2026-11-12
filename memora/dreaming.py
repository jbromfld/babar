"""Atomic, namespace-bound consolidation. No generative model runs here."""

import json
from uuid import UUID, uuid4

from psycopg2.extras import Json


class DreamingStore:
    def _dream_lock(self, cur):
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (self.config.namespace + ":dreaming",),
        )

    def dream_candidates(self, limit=5):
        from .store import public

        if not 1 <= limit <= 5:
            raise ValueError("Invalid group limit")
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """WITH active AS (SELECT * FROM memora_notes WHERE namespace=%s AND status='active' AND superseded_by IS NULL ORDER BY updated_at DESC,id LIMIT 200) SELECT a.id AS first,b.id AS second FROM active a
                JOIN active b ON a.namespace=b.namespace AND a.id<b.id
                WHERE a.namespace=%s AND a.status='active' AND b.status='active'
                AND a.superseded_by IS NULL AND b.superseded_by IS NULL
                AND a.memory_value->>'kind'=b.memory_value->>'kind'
                AND (a.primary_embedding <=> b.primary_embedding)<0.32
                ORDER BY a.primary_embedding <=> b.primary_embedding,a.id,b.id LIMIT 100""",
                (self.config.namespace, self.config.namespace),
            )
            pairs = cur.fetchall()
            groups, used = [], set()
            for pair in pairs:
                ids = [str(pair["first"]), str(pair["second"])]
                if used.intersection(ids):
                    continue
                used.update(ids)
                cur.execute(
                    "SELECT * FROM memora_notes WHERE namespace=%s AND id=ANY(%s::uuid[]) ORDER BY id",
                    (self.config.namespace, ids),
                )
                groups.append({"sources": [public(r) for r in cur.fetchall()]})
                if len(groups) == limit:
                    break
            return {"groups": groups}

    def consolidation_status(self, operation_key):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT result_id,undone FROM memora_consolidations WHERE namespace=%s AND operation_key=%s",
                (self.config.namespace, str(UUID(operation_key))),
            )
            row = cur.fetchone()
            return {
                "found": bool(row),
                "id": str(row["result_id"]) if row else None,
                "undone": row["undone"] if row else False,
            }

    def consolidate(self, note, sources, operation_key):
        from .store import Note

        note = Note.model_validate(note)
        if note.status != "active" or not 2 <= len(sources) <= 5:
            raise ValueError("Consolidation requires 2–5 active sources")
        expected = {str(UUID(s["id"])): int(s["revision"]) for s in sources}
        if len(expected) != len(sources):
            raise ValueError("Duplicate source")
        key = str(UUID(operation_key))
        identity = {
            "note": note.model_dump(mode="json"),
            "sources": sorted(expected.items()),
        }
        embedding = self.embedding(
            note.title + " " + note.text + " " + " ".join(note.cues)
        )
        with self.connect() as conn, conn.cursor() as cur:
            return self._consolidate(cur, note, expected, key, identity, embedding)

    def _consolidate(self, cur, note, expected, key, identity, embedding):
        from .store import StoreError, public

        self._dream_lock(cur)
        cur.execute(
            "SELECT * FROM memora_consolidations WHERE namespace=%s AND operation_key=%s",
            (self.config.namespace, key),
        )
        old = cur.fetchone()
        if old:
            if old["request"] != json.loads(json.dumps(identity)) or old["undone"]:
                raise StoreError(
                    "conflict", "Consolidation request changed or was undone."
                )
            return self._dream_result(cur, old["result_id"])
        cur.execute(
            "SELECT * FROM memora_notes WHERE namespace=%s AND id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
            (self.config.namespace, sorted(expected)),
        )
        rows = cur.fetchall()
        if len(rows) != len(expected) or any(
            r["revision"] != expected[str(r["id"])]
            or r["status"] != "active"
            or r["superseded_by"]
            or r["memory_value"]["kind"] != note.kind
            for r in rows
        ):
            raise StoreError("conflict", "A source changed or is no longer active.")
        if note.source_date.isoformat() != min(
            r["memory_value"]["source_date"] for r in rows
        ):
            # Dates retain their original meaning, not the consolidation date.
            raise ValueError("Use the earliest original source date")
        identifier = str(uuid4())
        snapshots = [public(r) for r in rows]
        cur.execute(
            """INSERT INTO memora_notes(namespace,id,create_key,primary_abstraction,primary_embedding,memory_value,cue_anchors,revision,status)
            VALUES(%s,%s,%s,%s,%s::vector,%s,%s,1,'active') RETURNING *""",
            (
                self.config.namespace,
                identifier,
                str(uuid4()),
                note.title,
                embedding,
                Json(note.model_dump(mode="json")),
                note.cues,
            ),
        )
        self._revision(cur, public(cur.fetchone()))
        for row in rows:
            cur.execute(
                "UPDATE memora_notes SET superseded_by=%s,revision=revision+1,updated_at=now() WHERE namespace=%s AND id=%s RETURNING *",
                (identifier, self.config.namespace, str(row["id"])),
            )
            self._revision(cur, public(cur.fetchone()))
        cur.execute(
            "INSERT INTO memora_consolidations(namespace,operation_key,result_id,request,sources) VALUES(%s,%s,%s,%s,%s)",
            (
                self.config.namespace,
                key,
                identifier,
                Json(identity),
                Json(snapshots),
            ),
        )
        return self._dream_result(cur, identifier)

    def _dream_result(self, cur, identifier):
        from .store import public

        cur.execute(
            "SELECT * FROM memora_notes WHERE namespace=%s AND id=%s",
            (self.config.namespace, str(identifier)),
        )
        return public(cur.fetchone())

    def undo_consolidation(self, operation_key, expected_revision):
        from .store import StoreError, public

        with self.connect() as conn, conn.cursor() as cur:
            self._dream_lock(cur)
            cur.execute(
                "SELECT * FROM memora_consolidations WHERE namespace=%s AND operation_key=%s FOR UPDATE",
                (self.config.namespace, str(UUID(operation_key))),
            )
            op = cur.fetchone()
            if not op or op["undone"]:
                raise StoreError(
                    "conflict", "Consolidation unavailable or already undone."
                )
            ids = [s["id"] for s in op["sources"]] + [str(op["result_id"])]
            cur.execute(
                "SELECT * FROM memora_notes WHERE namespace=%s AND id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
                (self.config.namespace, ids),
            )
            rows = {str(r["id"]): r for r in cur.fetchall()}
            target = rows.get(str(op["result_id"]))
            if (
                not target
                or (target["revision"] != expected_revision or target["revision"] != 1)
                or target["superseded_by"]
                or target["status"] != "active"
                or any(
                    s["id"] not in rows
                    or rows[s["id"]]["revision"] != s["revision"] + 1
                    or str(rows[s["id"]]["superseded_by"]) != str(op["result_id"])
                    for s in op["sources"]
                )
            ):
                raise StoreError(
                    "conflict",
                    "The consolidated family changed; review it before undoing.",
                )
            for source in op["sources"]:
                cur.execute(
                    "UPDATE memora_notes SET superseded_by=NULL,revision=revision+1,updated_at=now() WHERE namespace=%s AND id=%s RETURNING *",
                    (self.config.namespace, source["id"]),
                )
                self._revision(cur, public(cur.fetchone()))
            cur.execute(
                "UPDATE memora_notes SET status='abandoned',memory_value=jsonb_set(memory_value,'{status}','\"abandoned\"'),revision=revision+1,updated_at=now() WHERE namespace=%s AND id=%s RETURNING *",
                (self.config.namespace, str(op["result_id"])),
            )
            self._revision(cur, public(cur.fetchone()))
            cur.execute(
                "UPDATE memora_consolidations SET undone=true WHERE namespace=%s AND operation_key=%s",
                (self.config.namespace, str(UUID(operation_key))),
            )
            return {"undone": True}

    def forget_consolidation(self, id, expected_revision):
        from .store import StoreError

        identifier = str(UUID(id))
        with self.connect() as conn, conn.cursor() as cur:
            self._dream_lock(cur)
            cur.execute(
                "SELECT * FROM memora_consolidations WHERE namespace=%s",
                (self.config.namespace,),
            )
            operations = cur.fetchall()
            family = {identifier}
            changed = True
            while changed:
                before = len(family)
                for op in operations:
                    group = {str(op["result_id"]), *(s["id"] for s in op["sources"])}
                    if family.intersection(group):
                        family.update(group)
                changed = len(family) != before
            cur.execute(
                "SELECT id,revision FROM memora_notes WHERE namespace=%s AND id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE",
                (self.config.namespace, sorted(family)),
            )
            rows = {str(r["id"]): r["revision"] for r in cur.fetchall()}
            if rows.get(identifier) != expected_revision:
                raise StoreError(
                    "conflict", "Memory changed; reload before forgetting."
                )
            cur.execute(
                "DELETE FROM memora_consolidations WHERE namespace=%s AND result_id=ANY(%s::uuid[])",
                (self.config.namespace, sorted(family)),
            )
            cur.execute(
                "DELETE FROM memora_notes WHERE namespace=%s AND id=ANY(%s::uuid[])",
                (self.config.namespace, sorted(family)),
            )
            self._purge_dreams(cur, sorted(family))
            return {"forgotten": True, "count": len(family)}
