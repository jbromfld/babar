"""Explicit offline reindex after changing the runtime model identity."""

from psycopg2 import sql
from psycopg2.extras import Json

from .config import load_config
from .embedding import Embedder
from .setup import admin_connection
from .store import vector


def reindex(conn, config, embed):
    with conn.cursor() as cur:
        cur.execute("LOCK TABLE memora_notes IN ACCESS EXCLUSIVE MODE")
        cur.execute(
            sql.SQL(
                "ALTER TABLE memora_notes ADD COLUMN replacement_embedding vector({})"
            ).format(sql.Literal(config.dimension))
        )
        cur.execute(
            "SELECT namespace,id,primary_abstraction,memory_value,cue_anchors FROM memora_notes"
        )
        rows = cur.fetchall()
        for namespace, id, title, value, cues in rows:
            encoded = vector(
                embed(title + " " + value["text"] + " " + " ".join(cues)),
                config.dimension,
            )
            cur.execute(
                "UPDATE memora_notes SET replacement_embedding=%s::vector WHERE namespace=%s AND id=%s",
                (encoded, namespace, id),
            )
        cur.execute("ALTER TABLE memora_notes DROP COLUMN primary_embedding")
        cur.execute(
            "ALTER TABLE memora_notes RENAME COLUMN replacement_embedding TO primary_embedding"
        )
        cur.execute(
            "ALTER TABLE memora_notes ALTER COLUMN primary_embedding SET NOT NULL"
        )
        cur.execute(
            "CREATE INDEX memora_notes_embedding ON memora_notes USING hnsw(primary_embedding vector_cosine_ops)"
        )
        cur.execute(
            "UPDATE memora_model SET identity=%s WHERE singleton",
            (Json(config.identity),),
        )


def main():
    try:
        config = load_config()
        conn = admin_connection(config.database)
        try:
            with conn:
                reindex(conn, config, Embedder(config))
        finally:
            conn.close()
        print("Memora embeddings and model identity replaced atomically.")
    except Exception:
        raise SystemExit(
            "Reindex failed; existing embeddings were retained. Check admin credentials and offline model files."
        ) from None


if __name__ == "__main__":
    main()
