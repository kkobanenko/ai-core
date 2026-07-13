"""Тесты политики обрезки IO для Phoenix-трейсов."""

from ai_core.io_policy import maybe_truncate

TRUNCATED_SUFFIX = "…[truncated]"


def test_maybe_truncate_short_text_unchanged():
    """Короткий текст не обрезается."""
    text = "короткий промпт"
    assert maybe_truncate(text, max_chars=100) == text


def test_maybe_truncate_long_text_adds_suffix():
    """Длинный текст обрезается с суффиксом …[truncated]."""
    text = "a" * 100
    max_chars = 50
    result = maybe_truncate(text, max_chars=max_chars)
    assert result.endswith(TRUNCATED_SUFFIX)
    assert len(result) == max_chars
    assert result.startswith("a")


def test_maybe_truncate_none_returns_none():
    """None возвращается без изменений."""
    assert maybe_truncate(None, max_chars=10) is None


def test_maybe_truncate_empty_returns_empty():
    """Пустая строка возвращается без изменений."""
    assert maybe_truncate("", max_chars=10) == ""
