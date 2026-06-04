from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.config import ConfigError, load_cli_config


class MemoryServiceError(Exception):
    pass


class MemoryUserInputError(MemoryServiceError):
    pass


def build_memory_report(
    args: argparse.Namespace,
    *,
    prepare_import_paths: Callable[[], None],
) -> dict[str, Any]:
    try:
        prepare_import_paths()
        from ora_core.memory import LocalMemoryStore, build_memory_sync_preview, default_memory_store_path, memory_sync_non_actions

        store_path = args.store or str(default_memory_store_path())
        store = LocalMemoryStore(store_path)
    except Exception as exc:
        raise MemoryServiceError("local memory store is unavailable.") from exc

    schema_version = "yonerai-memory-boundary-cli/v0.1"
    scope = getattr(args, "scope", None) or None
    try:
        if args.memory_command == "add":
            default_scope = str(_load_memory_cli_config().get("memory_default_scope") or "local_private")
            effective_scope = scope or default_scope
            explicit_local_scope = scope in {"local", "local_private"}
            if not args.confirm_local and not explicit_local_scope:
                raise MemoryUserInputError("memory add requires --confirm-local or explicit --scope local.")
            record = store.add(_prompt_from_parts(args.text), tags=tuple(args.tag or ()), scope=effective_scope)
            return {
                "schema_version": schema_version,
                "ok": True,
                "operation": "add",
                "record": record.to_public_dict(),
                "cloud_synced": False,
                "store_path_output": False,
                "raw_prompt_persisted": False,
            }
        if args.memory_command == "status":
            report = store.status()
            all_records = store.list()
            config = _load_memory_cli_config()
            cloud_to_local_preview = (
                _memory_cloud_to_local_disabled_report(memory_sync_non_actions)
                if config.get("memory_cloud_to_local_preview_enabled") is not True
                else build_memory_sync_preview(all_records, direction="cloud_to_local")
            )
            local_to_cloud_preview = build_memory_sync_preview(all_records, direction="local_to_cloud")
            for preview in (cloud_to_local_preview, local_to_cloud_preview):
                local_refs = preview.pop("local_memory", [])
                preview["local_memory_refs_included"] = False
                preview["local_memory_ref_count"] = len(local_refs) if isinstance(local_refs, list) else 0
            report["recent_count"] = min(len(all_records), 5)
            report["recent_records_included"] = False
            report["sync_previews"] = {
                "cloud_to_local": cloud_to_local_preview,
                "local_to_cloud": local_to_cloud_preview,
            }
            return report
        if args.memory_command == "list":
            records = [record.to_public_dict() for record in store.list(scope=scope)]
            return {
                "schema_version": schema_version,
                "ok": True,
                "operation": "list",
                "records": records,
                "count": len(records),
                "cloud_synced": False,
                "store_path_output": False,
            }
        if args.memory_command == "forget":
            forgotten = store.forget(args.memory_id)
            return {
                "schema_version": schema_version,
                "ok": forgotten,
                "operation": "forget",
                "memory_id": args.memory_id,
                "forgotten": forgotten,
                "cloud_synced": False,
                "store_path_output": False,
            }
        if args.memory_command == "delete":
            deleted = store.delete(args.memory_id)
            return {
                "schema_version": schema_version,
                "ok": deleted,
                "operation": "delete",
                "memory_id": args.memory_id,
                "deleted": deleted,
                "cloud_synced": False,
                "store_path_output": False,
            }
        if args.memory_command == "export":
            return store.export() | {"operation": "export"}
        if args.memory_command == "sync" and getattr(args, "memory_sync_command", None) == "preview":
            direction = str(args.direction).replace("-", "_")
            if direction == "cloud_to_local":
                config = _load_memory_cli_config()
                if config.get("memory_cloud_to_local_preview_enabled") is not True:
                    return _memory_cloud_to_local_disabled_report(memory_sync_non_actions)
            return build_memory_sync_preview(
                store.list(include_inactive=True),
                direction=direction,  # type: ignore[arg-type]
                explicit_approval=bool(getattr(args, "approve", False)),
            )
    except MemoryUserInputError:
        raise
    except ValueError as exc:
        raise MemoryUserInputError(str(exc)) from exc
    except Exception as exc:
        raise MemoryServiceError("local memory operation failed; verify store permissions and JSONL format.") from exc
    raise MemoryUserInputError("unknown memory command")


def _load_memory_cli_config() -> dict[str, object]:
    try:
        return load_cli_config()
    except ConfigError as exc:
        raise MemoryUserInputError("YonerAI CLI config is invalid.") from exc


def _memory_cloud_to_local_disabled_report(non_actions: Callable[[], list[str]]) -> dict[str, Any]:
    return {
        "schema_version": "yonerai-memory-sync-boundary/v0.1",
        "ok": True,
        "operation": "sync_preview",
        "direction": "cloud_to_local",
        "preview_only": True,
        "sync_allowed": False,
        "official_backend_called": False,
        "sync_performed": False,
        "cloud_memory": {"selected_by_user": False, "raw_body_included": False},
        "local_memory_refs_included": False,
        "local_memory_ref_count": 0,
        "decision": {
            "direction": "cloud_to_local",
            "state": "blocked",
            "reason": "cloud_to_local_preview_disabled_by_config",
            "requires_explicit_approval": False,
            "private_content_excluded": True,
            "sync_performed": False,
        },
        "audit": {
            "schema_version": "yonerai-memory-sync-boundary/v0.1",
            "audit_reason": "cloud_to_local_preview_disabled_by_config",
            "actor": "local_user",
            "dry_run": True,
            "raw_private_content_logged": False,
            "pii_logged": False,
            "provider_keys_logged": False,
            "local_absolute_paths_logged": False,
        },
        "private_content_exclusion": {
            "local_private_excluded": True,
            "secret_like_excluded": True,
            "private_file_content_excluded": True,
            "local_node_payload_excluded": True,
            "raw_prompt_excluded": True,
        },
        "actions_not_performed": [*non_actions(), "cloud-to-local memory preview disabled by CLI config"],
    }


def _prompt_from_parts(parts: list[str] | tuple[str, ...]) -> str:
    prompt = " ".join(parts).strip()
    if not prompt:
        raise MemoryUserInputError("prompt must not be empty.")
    return prompt
