"""Explicit administrator-only provisioning. No budget credentials in runtime config."""

import argparse
import json
import os
import secrets
import tempfile
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json

from .config import Config

TABLES = ("memora_notes", "memora_revisions", "memora_model", "memora_migrations")


def admin_connection(database):
    host = os.environ.get("PGHOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Provisioning requires loopback PostgreSQL.")
    return psycopg2.connect(
        host=host,
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD"),
        dbname=database,
        connect_timeout=5,
    )


def migrate(conn, config):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(709401231)")
        cur.execute(
            Path(__file__)
            .with_name("schema.sql")
            .read_text()
            .replace("{dimension}", str(config.dimension))
        )
        cur.execute("SELECT max(version) FROM memora_migrations")
        version = cur.fetchone()[0]
        if version is not None and version != 1:
            raise ValueError("Unsupported Memora schema version.")
        cur.execute(
            "SELECT atttypmod FROM pg_attribute WHERE attrelid='public.memora_notes'::regclass AND attname='primary_embedding'"
        )
        if cur.fetchone()[0] != config.dimension:
            raise ValueError("Embedding dimension changed. Run explicit reindexing.")
        cur.execute("SELECT identity FROM memora_model WHERE singleton")
        row = cur.fetchone()
        if row and row[0] != config.identity:
            raise ValueError("Model identity changed. Run explicit reindexing instead.")
        cur.execute(
            "INSERT INTO memora_model(singleton,identity) VALUES(true,%s) ON CONFLICT DO NOTHING",
            (Json(config.identity),),
        )
        cur.execute(
            "INSERT INTO memora_migrations(version) VALUES(1) ON CONFLICT DO NOTHING"
        )


def atomic_config(path, config):
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".memora-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(
                json.dumps(
                    {
                        **config.model_dump(mode="json"),
                        "password": config.password.get_secret_value(),
                    },
                    indent=2,
                )
                + "\n"
            )
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify(conn, role):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit,
          EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid),
          EXISTS(SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid=r.oid AND deptype='o')
          FROM pg_roles r WHERE rolname=%s""",
            (role,),
        )
        row = cur.fetchone()
        if row is None or any(row):
            raise ValueError(
                "Memory role has unsafe attributes, ownership, or memberships."
            )
        cur.execute(
            """SELECT n.nspname,c.relname,
          has_table_privilege(%s,c.oid,'SELECT'),has_table_privilege(%s,c.oid,'INSERT'),
          has_table_privilege(%s,c.oid,'UPDATE'),has_table_privilege(%s,c.oid,'DELETE'),
          has_table_privilege(%s,c.oid,'TRUNCATE,REFERENCES,TRIGGER')
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relkind IN ('r','p','v','m','f') AND n.nspname NOT LIKE 'pg_%%' AND n.nspname<>'information_schema'""",
            (role,) * 5,
        )
        for schema, table, read, insert, update, delete, unsafe in cur.fetchall():
            editable = (
                table in ("memora_notes", "memora_revisions") and schema == "public"
            )
            allowed = table in TABLES and schema == "public"
            if (read, insert, update, delete, unsafe) != (
                allowed,
                editable,
                editable,
                editable,
                False,
            ):
                raise ValueError("Unexpected effective memory table privileges.")
        cur.execute(
            "SELECT has_database_privilege(%s,current_database(),'CREATE'), has_schema_privilege(%s,'public','CREATE')",
            (role, role),
        )
        if any(cur.fetchone()):
            raise ValueError(
                "Memory role can create objects. Remove its grants without changing shared PUBLIC permissions."
            )

        cur.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,))
        role_oid = cur.fetchone()[0]
        cur.execute(
            """SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT LIKE 'pg_%%' AND nspname <> 'information_schema' AND has_schema_privilege(%s,oid,'CREATE')),
          EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname <> 'information_schema'
            AND a.grantee IN (0,%s) AND a.is_grantable),
          EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname <> 'information_schema' AND x.grantee IN (0,%s)),
          EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.prosecdef
            AND n.nspname NOT LIKE 'pg_%%' AND n.nspname <> 'information_schema' AND has_function_privilege(%s,p.oid,'EXECUTE'))""",
            (role, role_oid, role_oid, role),
        )
        if any(cur.fetchone()):
            raise ValueError(
                "Unexpected schema, grant-option, column, or SECURITY DEFINER privileges."
            )


def provision(conn, config, rotate=False):
    with conn.cursor() as cur:
        cur.execute("SELECT oid FROM pg_database WHERE datname=current_database()")
        marker = "memora-v1:" + str(cur.fetchone()[0])
        cur.execute(
            "SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=%s",
            (config.user,),
        )
        existing = cur.fetchone()
        if existing and existing[0] != marker:
            raise ValueError("Refusing to modify an unrelated existing role.")
        if existing:
            # Do not repair ownership or membership, which can belong to another application.
            with conn.cursor() as check:
                check.execute(
                    """SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid),
                  EXISTS(SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid=r.oid AND deptype='o')
                  FROM pg_roles r WHERE rolname=%s""",
                    (config.user,),
                )
                if any(check.fetchone()):
                    raise ValueError(
                        "Managed role unexpectedly owns objects or has memberships."
                    )
        else:
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                ).format(sql.Identifier(config.user))
            )
            cur.execute(
                sql.SQL("COMMENT ON ROLE {} IS %s").format(sql.Identifier(config.user)),
                (marker,),
            )
        if not existing or rotate:
            # Only the verifier enters SQL; plaintext passwords are never logged in SQL.
            verifier = psycopg2.extensions.encrypt_password(
                config.password.get_secret_value(),
                config.user,
                conn,
                algorithm="scram-sha-256",
            )
            cur.execute(
                sql.SQL("ALTER ROLE {} PASSWORD %s").format(
                    sql.Identifier(config.user)
                ),
                (verifier,),
            )
        cur.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
                sql.Identifier(config.database), sql.Identifier(config.user)
            )
        )
        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(config.database), sql.Identifier(config.user)
            )
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(
                sql.Identifier(config.user)
            )
        )
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(config.user)
            )
        )
        cur.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(
                sql.Identifier(config.user)
            )
        )
        for table in TABLES:
            privileges = (
                sql.SQL("SELECT,INSERT,UPDATE,DELETE")
                if table in TABLES[:2]
                else sql.SQL("SELECT")
            )
            cur.execute(
                sql.SQL("GRANT {} ON {} TO {}").format(
                    privileges, sql.Identifier(table), sql.Identifier(config.user)
                )
            )
    verify(conn, config.user)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--database", default="babar_memory")
    parser.add_argument("--user", default="babar_memory")
    parser.add_argument("--rotate-password", action="store_true")
    args = parser.parse_args()
    try:
        if args.config.is_symlink():
            raise ValueError("Use a regular owner-only runtime file.")
        exists = args.config.exists()
        if exists:
            config = Config.model_validate_json(args.config.read_text())
            if config.namespace != args.namespace:
                raise ValueError(
                    "A runtime profile cannot be reassigned to another namespace."
                )
            if args.rotate_password:
                config = config.model_copy(
                    update={"password": secrets.token_urlsafe(32)}
                )
                config = Config.model_validate(config.model_dump())
        else:
            config = Config(
                host=os.environ.get("PGHOST", "127.0.0.1"),
                port=int(os.environ.get("PGPORT", "5432")),
                namespace=args.namespace,
                database=args.database,
                user=args.user,
                password=secrets.token_urlsafe(32),
            )
        bootstrap = admin_connection(os.environ.get("PGDATABASE", "postgres"))
        try:
            bootstrap.autocommit = True
            with bootstrap.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname=%s", (config.database,)
                )
                if not cur.fetchone():
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier(config.database)
                        )
                    )
        finally:
            bootstrap.close()
        conn = admin_connection(config.database)
        try:
            with conn:
                migrate(conn, config)
                if not exists and not args.rotate_password:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM pg_roles WHERE rolname=%s", (config.user,)
                        )
                        if cur.fetchone():
                            raise ValueError(
                                "Existing credentials missing. Recover explicitly with --rotate-password."
                            )
                provision(conn, config, rotate=args.rotate_password)
        finally:
            conn.close()
        check = psycopg2.connect(**config.connection())
        try:
            verify(check, config.user)
        finally:
            check.close()
        atomic_config(args.config, config)
        print(
            "Memora database and restricted runtime login verified; owner-only configuration saved."
        )
    except Exception:
        raise SystemExit(
            "Memora setup failed. Check local admin credentials, pgvector, role ownership/grants, and runtime credentials. For a managed role with lost credentials, use --rotate-password. No secrets were printed."
        ) from None


if __name__ == "__main__":
    main()
