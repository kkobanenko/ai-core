"""Тесты загрузки конфигурации Phoenix из переменных окружения."""

from ai_core.config import load_phoenix_config


def test_phoenix_enabled_default_false(monkeypatch):
    """PHOENIX_ENABLED по умолчанию false, если переменная не задана."""
    monkeypatch.delenv("PHOENIX_ENABLED", raising=False)
    cfg = load_phoenix_config()
    assert cfg.enabled is False


def test_phoenix_enabled_reads_endpoint_project_max_io_chars(monkeypatch):
    """При включённом Phoenix читаются endpoint, project_name и max_io_chars."""
    monkeypatch.setenv("PHOENIX_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces")
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "prozakupki-platform")
    monkeypatch.setenv("PHOENIX_TRACE_MAX_IO_CHARS", "8000")

    cfg = load_phoenix_config()

    assert cfg.enabled is True
    assert cfg.collector_endpoint == "http://phoenix:6006/v1/traces"
    assert cfg.project_name == "prozakupki-platform"
    assert cfg.max_io_chars == 8000


def test_trace_io_default_false(monkeypatch):
    monkeypatch.delenv("PHOENIX_TRACE_INCLUDE_IO", raising=False)
    assert load_phoenix_config().trace_include_io is False
