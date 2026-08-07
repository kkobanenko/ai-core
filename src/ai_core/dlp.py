"""Проверка исходящего payload на утечку исходных чувствительных значений (DLP)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class DlpDecision(str, Enum):
    """Результат outbound leak check."""

    OK = "ok"
    BLOCK_EXTERNAL_EGRESS = "block_external_egress"


@dataclass(frozen=True)
class DlpResult:
    """Итог проверки перед отправкой во внешний контур."""

    decision: DlpDecision
    reasons: tuple[str, ...] = ()


# Детекторы «сырых» паттернов, которые не должны уходить наружу после sanitize.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}"
)
_AUTH_RE = re.compile(r"(?i)authorization\s*[:=]\s*\S+")
_COOKIE_RE = re.compile(r"(?i)(?:cookie|set-cookie)\s*[:=]\s*\S+")
_SECRET_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9\-._~+/]+=*|api[_-]?key\s*[:=]\s*\S+"
    r"|sk-[A-Za-z0-9]{10,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)"
)


def _normalize(value: str) -> str:
    """Нормализация для сравнения: нижний регистр, без лишних пробелов."""
    return " ".join(value.strip().lower().split())


def outbound_leak_check(
    safe_payload: str,
    original_sensitive_values: list[str] | tuple[str, ...] | None = None,
) -> DlpResult:
    """Проверить, что в safe_payload нет исходных чувствительных значений и секретов.

    Возвращает OK или BLOCK_EXTERNAL_EGRESS.
    Не логирует сами значения — только типы причин.
    """
    reasons: list[str] = []
    payload = safe_payload or ""

    # 1) Явные оригиналы, которые вызывающий передал как «не должны утечь».
    for raw in original_sensitive_values or ():
        if not raw:
            continue
        if raw in payload or _normalize(raw) in _normalize(payload):
            reasons.append("original_sensitive_value_present")
            break

    # 2) Паттерны: email (кроме .invalid — наши суррогаты).
    for match in _EMAIL_RE.finditer(payload):
        email = match.group(0).lower()
        if email.endswith(".invalid"):
            continue
        reasons.append("email_pattern")
        break

    # 3) Телефоны (длинные цифровые последовательности).
    for match in _PHONE_RE.finditer(payload):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 10:
            # Синтетические номера из surrogate начинаются с 900555 — пропускаем.
            if digits.startswith("900555"):
                continue
            reasons.append("phone_pattern")
            break

    # 4) Authorization / cookies / secret-like.
    if _AUTH_RE.search(payload):
        reasons.append("authorization_header")
    if _COOKIE_RE.search(payload):
        reasons.append("cookie_header")
    if _SECRET_RE.search(payload):
        reasons.append("secret_pattern")

    if reasons:
        # Уникальные причины в стабильном порядке.
        unique = tuple(dict.fromkeys(reasons))
        return DlpResult(decision=DlpDecision.BLOCK_EXTERNAL_EGRESS, reasons=unique)

    return DlpResult(decision=DlpDecision.OK, reasons=())


def is_egress_allowed(result: DlpResult) -> bool:
    """Удобный хелпер: True если можно отправлять наружу."""
    return result.decision == DlpDecision.OK
