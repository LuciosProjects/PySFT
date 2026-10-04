"""Small standard-library web app for testing PySFT's ``fetchData`` routine."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from pysft.core.database import close_db, get_db_manager
from pysft.core.io import _parse_attributes
from pysft.lib.fetchFinancialData import fetchData

MAX_REQUEST_BYTES = 1_000_000
ALLOWED_MODES = {"all", "price", "info"}
PREVIEW_HTML = Path(__file__).with_name("fetch_preview.html")
ATTRIBUTE_OPTIONS_MARKER = "__CANONICAL_ATTRIBUTE_OPTIONS__"
# Prevent a preview fetch that was already running from refilling a cleared cache.
_cache_lock = Lock()


def _csv_values(
    value: object, field: str, *, default: str | None = None
) -> list[str]:
    """Accept a comma-separated string or list of strings and normalize it."""
    if value is None:
        if default is None:
            raise ValueError(f"Enter at least one {field.rstrip('s')}.")
        value = default
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        values = [item.strip() for item in value if item.strip()]
    else:
        raise TypeError(
            f"{field} must be a comma-separated string or a list of strings."
        )

    if not values:
        raise ValueError(f"Enter at least one {field.rstrip('s')}.")
    return values


def _optional_text(payload: Mapping[str, Any], field: str) -> str | None:
    """Read an optional text field, treating blank input as unset."""
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    value = value.strip()
    return value or None


def _validate_fetch_request(payload: object) -> dict[str, Any]:
    """Validate a browser request and map it to ``fetchData`` keyword arguments."""
    if not isinstance(payload, dict):
        raise TypeError("Request body must be a JSON object.")

    indicators = _csv_values(payload.get("indicators"), "indicators")
    raw_attributes = payload.get("attributes")
    if (
        raw_attributes is None
        or (isinstance(raw_attributes, str) and not raw_attributes.strip())
        or (isinstance(raw_attributes, list) and not raw_attributes)
    ):
        attributes = None
    else:
        attributes = _csv_values(raw_attributes, "attributes")

    mode = payload.get("mode", "all")
    if not isinstance(mode, str):
        raise TypeError("mode must be a string.")
    if mode not in ALLOWED_MODES:
        raise ValueError("mode must be one of: all, price, info.")

    period = _optional_text(payload, "period")
    start = _optional_text(payload, "start")
    end = _optional_text(payload, "end")
    if period and (start or end):
        raise ValueError("Choose either a period or a start/end date range, not both.")
    if bool(start) != bool(end):
        raise ValueError("Provide both start and end dates for a date range.")
    if start and end:
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError as exc:
            raise ValueError("Start and end dates must use YYYY-MM-DD format.") from exc
        if start_date > end_date:
            raise ValueError("Start date must be on or before end date.")

    return {
        "indicators": indicators,
        "attributes": attributes,
        "period": period,
        "start": start,
        "end": end,
        "mode": mode,
    }


def _json_default(value: object) -> Any:
    """Convert common array/scalar/date values to JSON-compatible values."""
    for method_name in ("tolist", "item", "isoformat"):
        method = getattr(value, method_name, None)
        if callable(method):
            return method()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class FetchPreviewRequestHandler(BaseHTTPRequestHandler):
    """Serve the test page and its same-origin fetch endpoint."""

    server_version = "PySFTPreview/0.1"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        try:
            body = json.dumps(
                payload, ensure_ascii=False, default=_json_default
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            body = json.dumps(
                {"error": f"Could not encode the response as JSON: {exc}"}
            ).encode("utf-8")

        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            try:
                html = PREVIEW_HTML.read_text(encoding="utf-8")
            except OSError as exc:
                self._send_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Could not load the fetch preview page: {exc}",
                )
                return
            if html.count(ATTRIBUTE_OPTIONS_MARKER) != 1:
                self._send_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Fetch preview page is missing its attribute options placeholder.",
                )
                return
            attribute_options = json.dumps(
                _parse_attributes("all"), ensure_ascii=False
            ).replace("<", "\\u003c")
            body = html.replace(
                ATTRIBUTE_OPTIONS_MARKER, attribute_options, 1
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/fetch", "/api/cache/clear"}:
            self._send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        raw_length = self.headers.get("Content-Length")
        try:
            content_length = int(raw_length or "")
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "A valid Content-Length is required.")
            return
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._send_error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body must be smaller than 1 MB.",
            )
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
            if path == "/api/cache/clear":
                self._clear_cache(payload)
                return
            fetch_args = _validate_fetch_request(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body must contain valid JSON.")
            return
        except (TypeError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        try:
            with _cache_lock:
                data = fetchData(**fetch_args)
        except ValueError as exc:
            self._send_error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"Invalid fetch input: {exc}",
            )
            return
        except Exception as exc:  # noqa: BLE001 - surface package/provider errors to tester
            message = str(exc).strip() or type(exc).__name__
            self._send_error(HTTPStatus.BAD_GATEWAY, f"Fetch failed: {message}")
            return

        self._send_json(HTTPStatus.OK, {"data": data})

    def _clear_cache(self, payload: object) -> None:
        """Clear only the fetch cache, with explicit confirmation and CSRF guard."""
        if (
            self.headers.get("X-PySFT-Preview") != "1"
            or self.headers.get_content_type() != "application/json"
        ):
            self._send_error(HTTPStatus.FORBIDDEN, "Use the preview's clear-cache control.")
            return
        if not isinstance(payload, dict) or payload.get("confirm") is not True:
            self._send_error(HTTPStatus.BAD_REQUEST, "Confirm clearing the fetch cache first.")
            return
        try:
            with _cache_lock:
                try:
                    cleared = get_db_manager().clear_cache()
                finally:
                    close_db()
        except (sqlite3.Error, RuntimeError) as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Could not clear fetch cache: {exc}")
            return
        self._send_json(HTTPStatus.OK, {"cleared": cleared})


def run(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Serve the local testing app on the given interface and port."""
    server = ThreadingHTTPServer((host, port), FetchPreviewRequestHandler)
    print(f"PySFT fetch preview running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PySFT fetch preview.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    args = parser.parse_args()
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()