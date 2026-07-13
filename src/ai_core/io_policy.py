"""Политика обрезки prompt/response перед записью в Phoenix-трейсы."""

from __future__ import annotations

# Суффикс, добавляемый к обрезанному тексту.
TRUNCATED_SUFFIX = "…[truncated]"


def maybe_truncate(text: str | None, max_chars: int) -> str | None:
    """Обрезать текст до max_chars символов, если он длиннее лимита.

    None и пустая строка возвращаются без изменений.
    При обрезке к концу добавляется суффикс ``…[truncated]``.
    Итоговая длина результата не превышает max_chars.
    """
    if text is None or text == "":
        return text
    if len(text) <= max_chars:
        return text

    suffix_len = len(TRUNCATED_SUFFIX)
    if max_chars <= suffix_len:
        return TRUNCATED_SUFFIX[:max_chars]

    keep_len = max_chars - suffix_len
    return text[:keep_len] + TRUNCATED_SUFFIX
