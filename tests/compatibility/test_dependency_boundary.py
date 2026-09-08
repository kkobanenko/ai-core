from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


FORBIDDEN_PREFIXES = (
    "langchain",
    "httpx",
    "openai",
    "mistral",
    "ollama",
    "ai_core.runtime",
    "ai_core.client",
    "ai_core.server",
)


def run_isolated_import_probe() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[2]
    script = f"""
import importlib.abc
import json
import sys

FORBIDDEN = {FORBIDDEN_PREFIXES!r}

class RejectInferenceDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + '.') for prefix in FORBIDDEN):
            raise ImportError('forbidden inference dependency: ' + fullname)
        return None

sys.meta_path.insert(0, RejectInferenceDependencies())
sys.path.insert(0, {str(repository_root / 'src')!r})

import ai_core

tracer = ai_core.init_tracing()
with ai_core.start_llm_span(workflow='dependency-probe') as span:
    ai_core.record_llm_result(span, status='ok')
ai_core.shutdown_tracing()

loaded = sorted(
    name for name in sys.modules
    if any(name == prefix or name.startswith(prefix + '.') for prefix in FORBIDDEN)
)
print(json.dumps({{
    'exports': sorted(ai_core.__all__),
    'tracer_is_none': tracer is None,
    'forbidden_loaded': loaded,
}}, sort_keys=True))
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR"}
    }
    environment["PHOENIX_ENABLED"] = "false"
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=repository_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_tracing_only_import_rejects_inference_dependency_loading() -> None:
    result = run_isolated_import_probe()
    assert result["tracer_is_none"] is True
    assert result["forbidden_loaded"] == []
    assert result["exports"] == [
        "AttributeValue",
        "PhoenixConfig",
        "init_tracing",
        "load_phoenix_config",
        "maybe_truncate",
        "record_llm_result",
        "sanitize_attributes",
        "shutdown_tracing",
        "start_llm_span",
    ]
