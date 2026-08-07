"""DLP: блокирует исходные PII и secret-паттерны."""

from ai_core.dlp import DlpDecision, outbound_leak_check
from ai_core.surrogate import SurrogateMode, apply_surrogate, clear_local_map


def setup_function():
    clear_local_map()


def teardown_function():
    clear_local_map()


def test_blocks_when_original_pii_still_present():
    original = "alice@example.com"
    result = outbound_leak_check(
        safe_payload=f"please email {original}",
        original_sensitive_values=[original],
    )
    assert result.decision == DlpDecision.BLOCK_EXTERNAL_EGRESS
    assert "original_sensitive_value_present" in result.reasons


def test_ok_after_surrogate_removes_original():
    original_email = "alice@example.com"
    sur = apply_surrogate(
        f"Contact {original_email}",
        mode=SurrogateMode.TOKENIZED,
    )
    result = outbound_leak_check(
        sur.safe_payload,
        original_sensitive_values=[original_email],
    )
    assert result.decision == DlpDecision.OK


def test_blocks_authorization_header_pattern():
    result = outbound_leak_check("Authorization: Bearer tokensecretvalue")
    assert result.decision == DlpDecision.BLOCK_EXTERNAL_EGRESS
    assert "authorization_header" in result.reasons or "secret_pattern" in result.reasons


def test_blocks_cookie_pattern():
    result = outbound_leak_check("Cookie: session=abc123")
    assert result.decision == DlpDecision.BLOCK_EXTERNAL_EGRESS
    assert "cookie_header" in result.reasons


def test_allows_invalid_synthetic_email():
    result = outbound_leak_check("user_deadbeef01@example.invalid")
    assert result.decision == DlpDecision.OK
