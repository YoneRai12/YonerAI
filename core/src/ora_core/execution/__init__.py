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
    "build_boundary_checks_for_task",
    "build_run_ledger_from_env",
    "execute_task",
]
