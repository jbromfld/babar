"""Trusted local stdio MCP server. No HTTP transport, sampling, SQL, or agent tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .config import load_config
from .embedding import Embedder
from .store import Store, StoreError


def build_server(store):
    server = FastMCP("Memora", log_level="CRITICAL")

    def call(method, *args):
        try:
            return {"ok": True, "data": getattr(store, method)(*args)}
        except StoreError as exc:
            return {"ok": False, "code": exc.code, "message": str(exc)}
        except (ValueError, ValidationError):
            return {"ok": False, "code": "invalid", "message": "Invalid memory fields."}
        except Exception:
            # Database and model exceptions may contain credentials or private text.
            return {
                "ok": False,
                "code": "unavailable",
                "message": "Local memory is unavailable. Check its database, migrations, and offline model configuration.",
            }

    @server.tool()
    def memory_status() -> dict:
        return call("status")

    @server.tool()
    def memory_search(query: str, limit: int = 3) -> dict:
        return call("search", query, limit)

    @server.tool()
    def memory_list(offset: int = 0, limit: int = 25) -> dict:
        return call("list", offset, limit)

    @server.tool()
    def memory_get(id: str) -> dict:
        return call("get", id)

    @server.tool()
    def memory_create(note: dict, create_key: str) -> dict:
        return call("create", note, create_key)

    @server.tool()
    def memory_update(id: str, note: dict, expected_revision: int) -> dict:
        return call("update", id, note, expected_revision)

    @server.tool()
    def memory_forget(id: str, expected_revision: int) -> dict:
        return call("forget", id, expected_revision)

    @server.tool()
    def memory_dream_candidates(limit: int = 5) -> dict:
        return call("dream_candidates", limit)

    @server.tool()
    def memory_consolidation_status(operation_key: str) -> dict:
        return call("consolidation_status", operation_key)

    @server.tool()
    def memory_consolidate(note: dict, sources: list[dict], operation_key: str) -> dict:
        return call("consolidate", note, sources, operation_key)

    @server.tool()
    def memory_undo_consolidation(operation_key: str, expected_revision: int) -> dict:
        return call("undo_consolidation", operation_key, expected_revision)

    @server.tool()
    def memory_forget_consolidation(id: str, expected_revision: int) -> dict:
        return call("forget_consolidation", id, expected_revision)

    @server.tool()
    def memory_dream_prepare(pass_key: str) -> dict:
        return call("dream_prepare", pass_key)

    @server.tool()
    def memory_dream_get(operation_key: str) -> dict:
        return call("dream_get", operation_key)

    @server.tool()
    def memory_dream_evaluate(operation_key: str, raw: str) -> dict:
        return call("dream_evaluate", operation_key, raw)

    @server.tool()
    def memory_dream_commit(
        operation_key: str, reviewed: bool = False, note: dict | None = None
    ) -> dict:
        return call("dream_commit", operation_key, reviewed, note)

    @server.tool()
    def memory_dream_cancel(operation_key: str) -> dict:
        return call("dream_cancel", operation_key)

    return server


def main():
    try:
        config = load_config()
        build_server(Store(config, Embedder(config))).run(transport="stdio")
    except Exception:
        # No exception dump to MCP stderr, which can otherwise leak configuration.
        raise SystemExit(
            "Memora could not start. Check its owner-only runtime configuration."
        ) from None


if __name__ == "__main__":
    main()
