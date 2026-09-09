from __future__ import annotations

import pytest

from tests.compatibility.ast_contract import ContractExtractionError, module_contract


SOURCE = '''
from dataclasses import dataclass
from enum import Enum
import httpx

__all__ = ["Config", "Mode", "run"]

@dataclass(frozen=True)
class Config:
    name: str
    timeout: float = 1.5

    def ready(self, *, strict: bool = False) -> bool:
        return True

class Mode(str, Enum):
    TEXT = "text"
    JSON = "json"

def run(value: str, /, count: int = 1, *, enabled: bool = True) -> str | None:
    return value
'''


def test_module_contract_extracts_exports_imports_and_public_shapes() -> None:
    contract = module_contract(SOURCE)

    assert contract["exports"] == ["Config", "Mode", "run"]
    assert contract["imports"] == ["dataclasses", "enum", "httpx"]
    assert contract["functions"]["run"] == {
        "positional_only": [{"name": "value", "annotation": "str", "default": None}],
        "positional": [{"name": "count", "annotation": "int", "default": "1"}],
        "keyword_only": [
            {"name": "enabled", "annotation": "bool", "default": "True"}
        ],
        "vararg": None,
        "kwarg": None,
        "returns": "str | None",
    }
    assert contract["classes"]["Config"]["decorators"] == ["dataclass(frozen=True)"]
    assert contract["classes"]["Config"]["fields"] == [
        {"name": "name", "annotation": "str", "default": None},
        {"name": "timeout", "annotation": "float", "default": "1.5"},
    ]
    assert contract["classes"]["Config"]["methods"]["ready"]["keyword_only"] == [
        {"name": "strict", "annotation": "bool", "default": "False"}
    ]
    assert contract["classes"]["Mode"]["enum_members"] == [
        {"name": "TEXT", "value": "text"},
        {"name": "JSON", "value": "json"},
    ]


def test_module_contract_rejects_dynamic_all() -> None:
    with pytest.raises(ContractExtractionError, match="literal __all__"):
        module_contract('__all__ = build_exports()')
