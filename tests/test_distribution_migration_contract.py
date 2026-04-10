from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


class _FakeColumn:
    def __init__(self, name: str, *_args, **_kwargs) -> None:
        self.name = name


class _FakeConstraint:
    def __init__(self, *_args, **_kwargs) -> None:
        self.name = None


class _FakeType:
    def __call__(self, *_args, **_kwargs):
        return self


class _BatchOp:
    def __init__(self, recorder: "_OpRecorder", table_name: str) -> None:
        self._recorder = recorder
        self._table_name = table_name

    def __enter__(self) -> "_BatchOp":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def create_index(self, name: str, columns: list[str], unique: bool = False) -> None:
        self._recorder.indexes.append((self._table_name, name, tuple(columns), bool(unique)))

    def drop_index(self, name: str) -> None:
        self._recorder.dropped_indexes.append((self._table_name, name))

    def f(self, name: str) -> str:
        return name


class _OpRecorder:
    def __init__(self) -> None:
        self.tables: list[tuple[str, tuple[str, ...]]] = []
        self.indexes: list[tuple[str, str, tuple[str, ...], bool]] = []
        self.dropped_indexes: list[tuple[str, str]] = []
        self.dropped_tables: list[str] = []

    def create_table(self, name: str, *elements, **kwargs) -> None:
        del kwargs
        column_names: list[str] = []
        for element in elements:
            col_name = getattr(element, "name", None)
            if isinstance(col_name, str):
                column_names.append(col_name)
        self.tables.append((name, tuple(column_names)))

    def batch_alter_table(self, table_name: str, schema=None) -> _BatchOp:
        del schema
        return _BatchOp(self, table_name)

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


def _load_revision_module(revision_path: Path, recorder: _OpRecorder):
    alembic_mod = types.ModuleType("alembic")
    alembic_mod.op = recorder
    sqlalchemy_mod = types.ModuleType("sqlalchemy")
    sqlalchemy_mod.Column = _FakeColumn
    sqlalchemy_mod.String = _FakeType()
    sqlalchemy_mod.JSON = _FakeType()
    sqlalchemy_mod.Integer = _FakeType()
    sqlalchemy_mod.DateTime = _FakeType()
    sqlalchemy_mod.ForeignKeyConstraint = _FakeConstraint
    sqlalchemy_mod.PrimaryKeyConstraint = _FakeConstraint
    sqlalchemy_mod.UniqueConstraint = _FakeConstraint

    prev_alembic = sys.modules.get("alembic")
    prev_sqlalchemy = sys.modules.get("sqlalchemy")
    sys.modules["alembic"] = alembic_mod
    sys.modules["sqlalchemy"] = sqlalchemy_mod

    try:
        spec = importlib.util.spec_from_file_location("distribution_revision_test", revision_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if prev_alembic is not None:
            sys.modules["alembic"] = prev_alembic
        else:
            sys.modules.pop("alembic", None)
        if prev_sqlalchemy is not None:
            sys.modules["sqlalchemy"] = prev_sqlalchemy
        else:
            sys.modules.pop("sqlalchemy", None)


def test_distribution_revision_includes_tool_calls_and_file_tables() -> None:
    revision_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "alembic"
        / "versions"
        / "9d2e4c3c0f31_add_distribution_file_tables.py"
    )
    recorder = _OpRecorder()
    module = _load_revision_module(revision_path, recorder)

    module.upgrade()

    table_names = [name for name, _cols in recorder.tables]
    assert table_names[:4] == [
        "tool_calls",
        "distribution_files",
        "distribution_file_tickets",
        "distribution_file_audit",
    ]

    table_columns = {name: cols for name, cols in recorder.tables}
    assert "tool_call_id" in table_columns["distribution_files"]
    assert "ticket_id" in table_columns["distribution_file_audit"]

    indexes = {(table, name) for table, name, _cols, _unique in recorder.indexes}
    assert ("tool_calls", "ix_tool_calls_run_id") in indexes
    assert ("tool_calls", "ix_tool_calls_user_id") in indexes
    assert ("distribution_files", "ix_distribution_files_tool_call_id") in indexes
