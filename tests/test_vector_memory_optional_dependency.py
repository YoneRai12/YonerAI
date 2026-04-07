from __future__ import annotations

import sys

import pytest

from src.services import vector_memory


def test_vector_memory_module_imports_without_chromadb() -> None:
    assert hasattr(vector_memory, "VectorMemory")


def test_vector_memory_raises_clear_error_when_optional_dependency_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "chromadb", None)

    with pytest.raises(RuntimeError, match="requirements-optional-memory.txt"):
        vector_memory._import_chromadb()
