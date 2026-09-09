from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.compatibility.historical_loader import load_v020_json_client


V020_SHA = "e479d0af314714a96c959a2ea677abdcb0942af7"


def _provider(harness: object, name: str):
    return harness.ProviderConfig(
        name=name,
        transport="fake",
        model=f"{name}-model",
        base_url="http://invalid.test",
        api_key="not-a-secret",
        api_key_optional=False,
        timeout_seconds=1.0,
    )


def _attempts(result: object) -> list[tuple[str, int, str, str]]:
    return [
        (
            item["provider"],
            item["attempt_index"],
            item["outcome"],
            item["reason"],
        )
        for item in result.attempt_summary
    ]


def test_v020_builds_lazily_and_falls_back_once_in_order() -> None:
    client_type, harness = load_v020_json_client(V020_SHA)
    harness.outcomes.update(
        {
            "primary": [TimeoutError("sensitive error text")],
            "fallback": [harness.message("{\"ok\": true}", model_name="actual-model")],
        }
    )
    client = client_type((_provider(harness, "primary"), _provider(harness, "fallback")))

    assert harness.build_names == []
    result = client.create_json_completion("system", "user")

    assert harness.build_names == ["primary", "fallback"]
    assert result.raw_content == '{"ok": true}'
    assert result.model_name == "actual-model"
    assert _attempts(result) == [
        ("primary", 1, "transport_error", "TimeoutError"),
        ("fallback", 2, "success", "ok"),
    ]


@pytest.mark.parametrize(
    "error_factory",
    [
        lambda h: h.httpx.TimeoutException("timeout"),
        lambda h: h.httpx.TransportError("transport"),
        lambda h: h.status_error(429),
        lambda h: h.status_error(500),
        lambda h: h.status_error(599),
    ],
)
def test_v020_fallback_eligible_errors_advance_to_next_provider(error_factory) -> None:
    client_type, harness = load_v020_json_client(V020_SHA)
    error = error_factory(harness)
    harness.outcomes.update(
        {
            "primary": [error],
            "fallback": [harness.message("ok")],
        }
    )

    result = client_type(
        (_provider(harness, "primary"), _provider(harness, "fallback"))
    ).create_json_completion("system", "user")

    assert harness.build_names == ["primary", "fallback"]
    assert [item["outcome"] for item in result.attempt_summary] == [
        "transport_error",
        "success",
    ]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_v020_terminal_4xx_stops_without_fallback(status: int) -> None:
    client_type, harness = load_v020_json_client(V020_SHA)
    terminal = harness.status_error(status)
    harness.outcomes.update(
        {
            "primary": [terminal],
            "fallback": [harness.message("must not run")],
        }
    )

    with pytest.raises(type(terminal)) as raised:
        client_type(
            (_provider(harness, "primary"), _provider(harness, "fallback"))
        ).create_json_completion("system", "user")

    assert raised.value is terminal
    assert harness.build_names == ["primary"]


def test_v020_exhaustion_attempts_each_ready_provider_once() -> None:
    client_type, harness = load_v020_json_client(V020_SHA)
    harness.outcomes.update(
        {
            "one": [TimeoutError("first")],
            "two": [harness.httpx.TransportError("second")],
        }
    )

    with pytest.raises(RuntimeError, match="second"):
        client_type((_provider(harness, "one"), _provider(harness, "two"))).create_json_completion(
            "system", "user"
        )

    assert harness.build_names == ["one", "two"]


def test_v020_returns_raw_content_without_json_schema_validation() -> None:
    client_type, harness = load_v020_json_client(V020_SHA)
    harness.outcomes["only"] = [
        harness.message("not-json", input_tokens=3, output_tokens=5)
    ]

    result = client_type((_provider(harness, "only"),)).create_json_completion(
        "system", "user"
    )

    assert result.raw_content == "not-json"
    assert (result.input_tokens, result.output_tokens) == (3, 5)
