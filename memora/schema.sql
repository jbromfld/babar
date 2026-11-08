-- Memora schema version 1: application-scoped, explicitly revised memory.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS memora_migrations (version integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS memora_model (singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), identity jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS memora_notes (
  namespace text NOT NULL, id uuid NOT NULL, create_key uuid NOT NULL,
  primary_abstraction text NOT NULL, primary_embedding vector({dimension}) NOT NULL,
  memory_value jsonb NOT NULL, cue_anchors text[] NOT NULL DEFAULT '{}',
  revision integer NOT NULL CHECK(revision > 0),
  status text NOT NULL CHECK(status IN ('active','completed','abandoned')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,id), UNIQUE(namespace,create_key)
);
CREATE TABLE IF NOT EXISTS memora_revisions (
  namespace text NOT NULL, note_id uuid NOT NULL, revision integer NOT NULL,
  document jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(namespace,note_id,revision),
  FOREIGN KEY(namespace,note_id) REFERENCES memora_notes(namespace,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS memora_notes_namespace ON memora_notes(namespace,status,created_at,id);
CREATE INDEX IF NOT EXISTS memora_notes_embedding ON memora_notes USING hnsw(primary_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS memora_notes_cues ON memora_notes USING gin(cue_anchors);
