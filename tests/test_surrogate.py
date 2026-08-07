"""Суррогатизация: tokenize, format-preserving, secrets drop/block."""

from ai_core.surrogate import (
    SecretAction,
    SurrogateMode,
    apply_surrogate,
    clear_local_map,
    get_local_map_snapshot,
)


def setup_function():
    clear_local_map()


def teardown_function():
    clear_local_map()


def test_tokenize_email_and_phone():
    text = "Contact alice@example.com or +1-555-123-4567 please"
    result = apply_surrogate(text, mode=SurrogateMode.TOKENIZED)
    assert "alice@example.com" not in result.safe_payload
    assert "+1-555-123-4567" not in result.safe_payload
    assert "[EMAIL_" in result.safe_payload or "EMAIL" in str(result.surrogate_manifest)
    assert result.local_surrogate_map
    # Map содержит оригиналы локально
    assert "alice@example.com" in result.local_surrogate_map.values()


def test_format_preserving_email_uses_invalid_domain():
    text = "mail me at bob@company.com thanks"
    result = apply_surrogate(text, mode=SurrogateMode.FORMAT_PRESERVING_SYNTHETIC)
    assert "bob@company.com" not in result.safe_payload
    assert ".invalid" in result.safe_payload
    assert "bob@company.com" in result.local_surrogate_map.values()


def test_secrets_are_dropped_never_surrogated():
    text = "token Authorization: Bearer abcdef123456 and ok"
    result = apply_surrogate(text, mode=SurrogateMode.TOKENIZED, secret_action=SecretAction.DROP)
    assert "Bearer abcdef123456" not in result.safe_payload
    assert result.dropped_secrets >= 1
    # Секрет не должен появиться как значение в map суррогатов
    assert "Bearer abcdef123456" not in result.local_surrogate_map.values()


def test_secrets_block_stops_processing():
    text = "Authorization: Bearer supersecretvalue999"
    result = apply_surrogate(text, secret_action=SecretAction.BLOCK)
    assert result.blocked is True
    assert result.safe_payload == ""


def test_clear_local_map_empties_request_scoped_state():
    apply_surrogate("user@example.com")
    assert get_local_map_snapshot()
    clear_local_map()
    assert get_local_map_snapshot() == {}
