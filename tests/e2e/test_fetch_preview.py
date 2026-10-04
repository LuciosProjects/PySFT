"""Browser-facing fetch preview behavior with a controlled fetch result."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest

from pysft import fetch_preview
from pysft.core.io import _parse_attributes
from pysft.fetch_preview import FetchPreviewRequestHandler

pytestmark = [pytest.mark.e2e]


@contextmanager
def _preview_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FetchPreviewRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request_json(
    url: str, *, method: str = "GET", payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], str]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        headers={
            **({"Content-Type": "application/json"} if body is not None else {}),
            **(headers or {}),
        },
        method=method,
    )
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        raw_body = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        return response.status, json.loads(raw_body), content_type


def test_preview_page_is_served_with_browser_interface() -> None:
    with _preview_server() as base_url, urlopen(
        base_url + "/", timeout=5
    ) as response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        html = response.read().decode("utf-8")

    assert status == 200
    assert content_type.startswith("text/html")
    assert "Fetch console" in html
    assert "/api/fetch" in html
    assert 'id="attributesToggle"' in html
    assert 'aria-controls="attributesMenu"' in html
    assert "Select all" in html
    assert "Clear selection" in html
    assert "Leave blank to use the fetch mode’s default fields" in html
    assert "__CANONICAL_ATTRIBUTE_OPTIONS__" not in html
    options_marker = '<script id="canonicalAttributes" type="application/json">'
    options_start = html.index(options_marker) + len(options_marker)
    options_end = html.index("</script>", options_start)
    assert json.loads(html[options_start:options_end]) == _parse_attributes("all")
    assert "function selectedAttributes()" in html
    assert 'attributes: selectedAttributes().join(", ")' in html
    assert "checkbox.checked = false;" in html
    assert "checkbox.defaultChecked = false;" in html
    assert "if (attributes.length === 0)" not in html
    assert html.count("setAttributeSelection([]);") >= 2
    assert html.count("setAttributeSelection(canonicalAttributes);") == 1
    assert 'id="clearCacheButton"' in html
    assert "/api/cache/clear" in html
    assert "window.confirm" in html


@pytest.mark.parametrize(
    ("confirm", "guard_header", "expected_status"),
    [(True, True, 200), (False, True, 400), (True, False, 403)],
)
def test_clear_cache_requires_confirmation_and_keeps_schema(
    pysft_env, confirm, guard_header, expected_status
):
    connection = pysft_env.manager.connection
    assert connection is not None
    with connection:
        connection.execute(
            "INSERT INTO indicator_attributes "
            "(indicator, attribute, value_json, fetched_at) VALUES (?, ?, ?, ?)",
            ("5111422", "currency", '"ILS"', "2026-10-01 12:00:00"),
        )
        connection.execute(
            "INSERT INTO price_history (indicator,date,close,fetched_at) VALUES (?,?,?,?)",
            ("5111422", "2026-10-01", 159.5, "2026-10-01 12:00:00"),
        )
    with _preview_server() as base_url:
        status, payload, _ = _request_json(
            base_url + "/api/cache/clear",
            method="POST",
            payload={"confirm": confirm},
            headers={"X-PySFT-Preview": "1"} if guard_header else {},
        )
    assert status == expected_status
    if expected_status == 200:
        assert payload == {"cleared": {"indicator_attributes": 1, "price_history": 1}}
    expected_count = 0 if expected_status == 200 else 1
    for query in (
        "SELECT COUNT(*) FROM indicator_attributes",
        "SELECT COUNT(*) FROM price_history",
    ):
        assert connection.execute(query).fetchone()[0] == expected_count


def test_clear_cache_failure_is_reported(monkeypatch):
    def unavailable_cache():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(fetch_preview, "get_db_manager", unavailable_cache)
    with _preview_server() as base_url:
        status, payload, _ = _request_json(
            base_url + "/api/cache/clear",
            method="POST",
            payload={"confirm": True},
            headers={"X-PySFT-Preview": "1"},
        )
    assert status == 500
    assert "Could not clear fetch cache: database is locked" in payload["error"]


def test_fetch_endpoint_passes_period_mode_and_returns_complete_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_result = {
        "AAPL": {"dates": ["2026-10-01"], "price": [100.25], "volume": [2500]},
        "MSFT": {"dates": ["2026-10-01"], "price": [210.5], "volume": [1800]},
    }
    calls: list[dict[str, Any]] = []

    def controlled_fetch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return fetch_result

    monkeypatch.setattr(fetch_preview, "fetchData", controlled_fetch)
    with _preview_server() as base_url:
        status, payload, content_type = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload={
                "indicators": " AAPL, MSFT ",
                "attributes": "price, volume",
                "period": "1mo",
                "mode": "price",
            },
        )

    assert status == 200
    assert content_type.startswith("application/json")
    assert payload == {"data": fetch_result}
    assert calls == [
        {
            "indicators": ["AAPL", "MSFT"],
            "attributes": ["price", "volume"],
            "period": "1mo",
            "start": None,
            "end": None,
            "mode": "price",
        }
    ]


def test_fetch_endpoint_passes_date_range_and_info_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def controlled_fetch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"AAPL": {"name": "Apple Inc.", "currency": "USD"}}

    monkeypatch.setattr(fetch_preview, "fetchData", controlled_fetch)
    with _preview_server() as base_url:
        status, payload, _ = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload={
                "indicators": ["AAPL"],
                "attributes": ["price"],
                "start": "2026-01-01",
                "end": "2026-01-31",
                "mode": "info",
            },
        )

    assert status == 200
    assert payload["data"]["AAPL"]["name"] == "Apple Inc."
    assert calls == [
        {
            "indicators": ["AAPL"],
            "attributes": ["price"],
            "period": None,
            "start": "2026-01-01",
            "end": "2026-01-31",
            "mode": "info",
        }
    ]


@pytest.mark.parametrize(
    ("mode", "attribute_value"),
    [("all", ""), ("price", "  "), ("info", None)],
)
def test_fetch_endpoint_uses_mode_defaults_when_attributes_are_blank(
    monkeypatch: pytest.MonkeyPatch, mode: str, attribute_value: str | None
) -> None:
    calls: list[dict[str, Any]] = []

    def controlled_fetch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"AAPL": {"dates": [], "price": []}}

    monkeypatch.setattr(fetch_preview, "fetchData", controlled_fetch)
    request_payload: dict[str, Any] = {"indicators": "AAPL", "mode": mode}
    if attribute_value is not None:
        request_payload["attributes"] = attribute_value
    with _preview_server() as base_url:
        status, payload, _ = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload=request_payload,
        )

    assert status == 200
    assert payload == {"data": {"AAPL": {"dates": [], "price": []}}}
    assert calls == [
        {
            "indicators": ["AAPL"],
            "attributes": None,
            "period": None,
            "start": None,
            "end": None,
            "mode": mode,
        }
    ]


def test_fetch_endpoint_serializes_numpy_arrays_and_scalars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_result = {
        "AAPL": {
            "price": np.array([100.25, 101.5]),
            "volume": np.array([1200, 1400], dtype=np.int64),
            "market_cap": np.float64(1_000_000.5),
        }
    }

    def controlled_fetch(**kwargs: Any) -> dict[str, Any]:
        return fetch_result

    monkeypatch.setattr(fetch_preview, "fetchData", controlled_fetch)
    with _preview_server() as base_url:
        status, payload, content_type = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload={"indicators": "AAPL"},
        )

    assert status == 200
    assert content_type.startswith("application/json")
    assert payload == {
        "data": {
            "AAPL": {
                "price": [100.25, 101.5],
                "volume": [1200, 1400],
                "market_cap": 1_000_000.5,
            }
        }
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "Enter at least one indicator."),
        ({"indicators": "AAPL", "mode": "bad"}, "mode must be one of"),
        (
            {"indicators": "AAPL", "start": "2026-01-01"},
            "Provide both start and end dates",
        ),
        (
            {"indicators": "AAPL", "period": "1mo", "start": "2026-01-01", "end": "2026-01-31"},
            "Choose either a period or a start/end date range",
        ),
        (
            {"indicators": "AAPL", "attributes": ","},
            "Enter at least one attribute.",
        ),
    ],
)
def test_invalid_request_is_explained_without_calling_fetch(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], message: str
) -> None:
    def unexpected_fetch(**kwargs: Any) -> dict[str, Any]:
        pytest.fail(f"fetchData should not run for invalid input: {kwargs}")

    monkeypatch.setattr(fetch_preview, "fetchData", unexpected_fetch)
    with _preview_server() as base_url:
        status, response, _ = _request_json(
            base_url + "/api/fetch", method="POST", payload=payload
        )

    assert status == 400
    assert message in response["error"]


def test_fetch_failure_is_returned_as_a_readable_json_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_fetch(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Provider is temporarily unavailable")

    monkeypatch.setattr(fetch_preview, "fetchData", failed_fetch)
    with _preview_server() as base_url:
        status, payload, content_type = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload={"indicators": "AAPL"},
        )

    assert status == 502
    assert content_type.startswith("application/json")
    assert payload == {"error": "Fetch failed: Provider is temporarily unavailable"}


def test_fetch_argument_error_is_returned_as_unprocessable_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_fetch(**kwargs: Any) -> dict[str, Any]:
        raise ValueError("Unsupported attribute: invalid_field")

    monkeypatch.setattr(fetch_preview, "fetchData", invalid_fetch)
    with _preview_server() as base_url:
        status, payload, _ = _request_json(
            base_url + "/api/fetch",
            method="POST",
            payload={"indicators": "AAPL", "attributes": "invalid_field"},
        )

    assert status == 422
    assert payload == {"error": "Invalid fetch input: Unsupported attribute: invalid_field"}