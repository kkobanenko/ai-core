"""Локальная суррогатизация PII перед отправкой во внешние провайдеры.

ВАЖНО:
- local_surrogate_map хранит соответствие оригинал ↔ суррогат ТОЛЬКО локально.
- Этот map НИКОГДА нельзя отправлять провайдеру, писать в логи, traces или Phoenix.
- После обработки запроса вызывайте clear_local_map().
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SurrogateMode(str, Enum):
    """Режим замены чувствительных значений."""

    TOKENIZED = "tokenized"
    FORMAT_PRESERVING_SYNTHETIC = "format_preserving_synthetic"


class EntityKind(str, Enum):
    """Типы сущностей, которые умеем суррогатировать."""

    PHONE = "phone"
    EMAIL = "email"
    PERSON_NAME = "person_name"
    ADDRESS = "address"
    ACCOUNT_IDENTIFIER = "account_identifier"
    URL_USERINFO = "url_userinfo"
    URL_SECRET_QUERY = "url_secret_query"
    FORM_FREE_TEXT = "form_free_text"
    OTHER_CONFIGURED_PII = "other_configured_pii"
    # SECRET-like: никогда не суррогатируем — только DROP/BLOCK.
    SECRET = "secret"


class SecretAction(str, Enum):
    """Действие для SECRET-подобных значений."""

    DROP = "drop"
    BLOCK = "block"


@dataclass(frozen=True)
class DetectedEntity:
    """Найденная сущность в payload."""

    kind: EntityKind
    original_value: str
    start: int
    end: int


@dataclass
class SurrogateResult:
    """Результат суррогатизации одного запроса.

    safe_payload — то, что можно отправить провайдеру.
    surrogate_manifest — обезличенный список замен (вид сущности, токен), без оригиналов.
    local_surrogate_map — ТОЛЬКО локально; не в провайдер/логи/traces.
    blocked — True, если встретили SECRET с действием BLOCK.
    dropped_secrets — сколько SECRET значений выбросили (DROP).
    """

    safe_payload: str
    # Манифест без оригинальных значений (безопасно для метаданных).
    surrogate_manifest: list[dict[str, str]] = field(default_factory=list)
    # ЛОКАЛЬНЫЙ map: surrogate_token -> original_value. НЕ экспортировать.
    local_surrogate_map: dict[str, str] = field(default_factory=dict)
    blocked: bool = False
    dropped_secrets: int = 0


# Простые паттерны детекции (junior-friendly, без тяжёлых NLP).
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}"
)
# Паттерны «похоже на секрет»: Bearer, api_key=, sk-...
_SECRET_RE = re.compile(
    r"(?i)(?:authorization\s*:\s*\S+|bearer\s+[A-Za-z0-9\-._~+/]+=*"
    r"|api[_-]?key\s*[:=]\s*\S+|sk-[A-Za-z0-9]{10,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)"
)


# Request-scoped map текущего потока обработки (один процесс / один запрос).
_LOCAL_MAP: dict[str, str] = {}
_COUNTERS: dict[str, int] = {}


def clear_local_map() -> None:
    """Очистить локальный surrogate map и счётчики после завершения запроса."""
    _LOCAL_MAP.clear()
    _COUNTERS.clear()


def get_local_map_snapshot() -> dict[str, str]:
    """Копия локального map (только для тестов/локального reverse; не логировать)."""
    return dict(_LOCAL_MAP)


def _next_token(kind: EntityKind) -> str:
    """Сгенерировать стабильный в рамках запроса токен вида [EMAIL_1]."""
    key = kind.value
    _COUNTERS[key] = _COUNTERS.get(key, 0) + 1
    return f"[{kind.value.upper()}_{_COUNTERS[key]}]"


def _synthetic_email(original: str) -> str:
    """Формат-сохраняющий email с доменом .invalid (RFC 2606)."""
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:10]
    return f"user_{digest}@example.invalid"


def _synthetic_phone(original: str) -> str:
    """Формат-сохраняющий телефон: оставляем цифры, но подменяем на синтетику."""
    digits = re.sub(r"\D", "", original)
    # Фиксированный синтетический номер той же длины (не настоящий).
    synth_digits = ("900555" + "0" * 20)[: max(len(digits), 10)]
    # Простая маска: если был +, сохраняем.
    if original.strip().startswith("+"):
        return "+" + synth_digits
    return synth_digits


def _is_secret_kind(kind: EntityKind) -> bool:
    return kind == EntityKind.SECRET


def detect_entities(text: str) -> list[DetectedEntity]:
    """Найти сущности в тексте (секрет > email > phone по приоритету перекрытий)."""
    found: list[DetectedEntity] = []

    for match in _SECRET_RE.finditer(text):
        found.append(
            DetectedEntity(EntityKind.SECRET, match.group(0), match.start(), match.end())
        )
    for match in _EMAIL_RE.finditer(text):
        found.append(
            DetectedEntity(EntityKind.EMAIL, match.group(0), match.start(), match.end())
        )
    for match in _PHONE_RE.finditer(text):
        # Отсекаем слишком короткие «номера» (шум).
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 10:
            continue
        found.append(
            DetectedEntity(EntityKind.PHONE, match.group(0), match.start(), match.end())
        )

    # Убираем перекрытия: более ранний и SECRET побеждают.
    found.sort(key=lambda e: (e.start, -(e.end - e.start)))
    cleaned: list[DetectedEntity] = []
    last_end = -1
    for entity in found:
        if entity.start < last_end:
            continue
        cleaned.append(entity)
        last_end = entity.end
    return cleaned


def apply_surrogate(
    payload: str,
    mode: SurrogateMode = SurrogateMode.TOKENIZED,
    secret_action: SecretAction = SecretAction.DROP,
    extra_entities: list[DetectedEntity] | None = None,
) -> SurrogateResult:
    """Суррогатировать payload. SECRET никогда не суррогатируется — DROP или BLOCK.

    local_surrogate_map обновляется в модульном request-scoped состоянии
    и дублируется в результате. Не передавайте map наружу.
    """
    entities = detect_entities(payload)
    if extra_entities:
        entities = list(entities) + list(extra_entities)
        entities.sort(key=lambda e: (e.start, -(e.end - e.start)))

    if not entities:
        return SurrogateResult(safe_payload=payload)

    # Идём с конца, чтобы индексы не сдвигались.
    entities_rev = sorted(entities, key=lambda e: e.start, reverse=True)
    text = payload
    manifest: list[dict[str, str]] = []
    local_map: dict[str, str] = {}
    dropped = 0

    for entity in entities_rev:
        if _is_secret_kind(entity.kind):
            if secret_action == SecretAction.BLOCK:
                return SurrogateResult(
                    safe_payload="",
                    surrogate_manifest=manifest,
                    local_surrogate_map=dict(_LOCAL_MAP),
                    blocked=True,
                    dropped_secrets=dropped,
                )
            # DROP: вырезаем секрет без замены на суррогат.
            text = text[: entity.start] + text[entity.end :]
            dropped += 1
            manifest.append({"kind": entity.kind.value, "action": "drop"})
            continue

        if mode == SurrogateMode.TOKENIZED:
            token = _next_token(entity.kind)
            replacement = token
        else:
            # FORMAT_PRESERVING_SYNTHETIC
            if entity.kind == EntityKind.EMAIL:
                replacement = _synthetic_email(entity.original_value)
            elif entity.kind == EntityKind.PHONE:
                replacement = _synthetic_phone(entity.original_value)
            else:
                # Для прочих — токен + пометка synthetic.
                replacement = _next_token(entity.kind)

        text = text[: entity.start] + replacement + text[entity.end :]
        # Map только локально: surrogate -> original.
        local_map[replacement] = entity.original_value
        _LOCAL_MAP[replacement] = entity.original_value
        # В манифест — без оригинала.
        manifest.append(
            {
                "kind": entity.kind.value,
                "surrogate": replacement,
                "mode": mode.value,
            }
        )

    return SurrogateResult(
        safe_payload=text,
        surrogate_manifest=list(reversed(manifest)),
        local_surrogate_map=local_map,
        blocked=False,
        dropped_secrets=dropped,
    )


def surrogate_structured(
    data: Any,
    mode: SurrogateMode = SurrogateMode.TOKENIZED,
    secret_action: SecretAction = SecretAction.DROP,
) -> SurrogateResult:
    """Упрощённо: сериализуем dict/list в строку через str() и суррогатируем.

    Для junior-friendly API; продакшен-клиенты могут вызывать apply_surrogate
    на конкретных полях сами.
    """
    if isinstance(data, str):
        return apply_surrogate(data, mode=mode, secret_action=secret_action)
    return apply_surrogate(str(data), mode=mode, secret_action=secret_action)
