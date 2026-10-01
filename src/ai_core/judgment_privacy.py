"""Граница privacy/egress для judgment до любого вызова провайдера."""

from __future__ import annotations

from ai_core.judgment_contracts import JudgmentExecutionMode, JudgmentRequest
from ai_core.judgment_errors import JudgmentError, JudgmentErrorCategory, judgment_error
from ai_core.privacy import DataClass, is_egress_eligible
from ai_core.provider_catalog import NetworkBoundary


# Классы данных, допустимые для hosted judgment (вне локального контура).
_HOSTED_JUDGMENT_DATA_CLASSES = frozenset(
    {
        DataClass.SYNTHETIC,
        DataClass.PUBLIC_NO_PII,
    }
)


def evaluate_judgment_privacy(request: JudgmentRequest) -> JudgmentError | None:
    """Fail-closed: проверка до mock/будущего transport."""

    if request.data_class is DataClass.SECRET:
        return judgment_error(
            JudgmentErrorCategory.PRIVACY_EGRESS_DENIED,
            "secret data class is denied for judgment execution",
        )

    if request.execution_mode is JudgmentExecutionMode.LOCAL_NO_EGRESS:
        # Локальное исполнение без egress: SECRET уже отсечён выше.
        return None

    if request.execution_mode is not JudgmentExecutionMode.HOSTED_EGRESS:
        return judgment_error(
            JudgmentErrorCategory.INVALID_REQUEST,
            "unknown judgment execution mode",
        )

    if request.data_class not in _HOSTED_JUDGMENT_DATA_CLASSES:
        return judgment_error(
            JudgmentErrorCategory.PRIVACY_EGRESS_DENIED,
            "hosted judgment requires synthetic or public_no_pii classification",
        )

    # Hosted judgment трактуем как внешний egress (как EXTERNAL в текстовом контуре).
    if not is_egress_eligible(
        data_class=request.data_class,
        outbound_form=request.outbound_form,
        network_boundary=NetworkBoundary.EXTERNAL,
        request_egress_authorized=request.request_egress_authorized,
    ):
        return judgment_error(
            JudgmentErrorCategory.PRIVACY_EGRESS_DENIED,
            "egress not authorized for hosted judgment",
        )

    return None


__all__ = [
    "evaluate_judgment_privacy",
]
