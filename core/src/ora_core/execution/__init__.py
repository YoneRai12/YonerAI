from .boundaries import (
    SearchBoundaryAdapter,
    ToolBoundaryAdapter,
    build_boundary_checks_for_task,
)
from .ledger import (
    ExecutionEvent,
    ExecutionRun,
    ExecutionStatus,
    FileRunLedger,
    InMemoryRunLedger,
    build_run_ledger_from_env,
)
from .legacy_text import legacy_text_normalizer_status, normalize_legacy_generated_text


def build_auto_runtime_report(*args, **kwargs):
    from .auto_runtime import build_auto_runtime_report as _build_auto_runtime_report

    return _build_auto_runtime_report(*args, **kwargs)


def build_auto_runtime_status_report(*args, **kwargs):
    from .auto_runtime import build_auto_runtime_status_report as _build_auto_runtime_status_report

    return _build_auto_runtime_status_report(*args, **kwargs)


def execute_task(*args, **kwargs):
    from .spine import execute_task as _execute_task

    return _execute_task(*args, **kwargs)


def __getattr__(name: str):
    if name == "ExecutionResult":
        from .spine import ExecutionResult

        return ExecutionResult
    raise AttributeError(name)

__all__ = [
    "ExecutionEvent",
    "ExecutionResult",
    "ExecutionRun",
    "ExecutionStatus",
    "FileRunLedger",
    "InMemoryRunLedger",
    "SearchBoundaryAdapter",
    "ToolBoundaryAdapter",
    "build_auto_runtime_report",
    "build_auto_runtime_status_report",
    "build_boundary_checks_for_task",
    "build_run_ledger_from_env",
    "execute_task",
    "legacy_text_normalizer_status",
    "normalize_legacy_generated_text",
]
