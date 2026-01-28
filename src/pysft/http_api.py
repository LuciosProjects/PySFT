"""
Minimal HTTP API for PySFT using the standard library.

Provides endpoints:
  - GET /health
  - GET /fetch?indicators=MSFT,AAPL&attributes=price,volume&period=1mo
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from pysft.lib.fetchFinancialData import fetch_data_as_dict


def _split_csv(value: str | None) -> list[str] | None:
    """Split a comma-separated query parameter into a list."""
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


class PySFTRequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the PySFT API."""
    server_version = "PySFTHTTP/0.1"

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        """Send a JSON response with the given HTTP status."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        """Send an error response as JSON."""
        self._send_json(status, {"error": message})

    def do_GET(self) -> None:  # noqa: N802 (HTTPServer naming convention)
        """Handle GET requests for health and fetch endpoints."""
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if parsed.path == "/fetch":
            params = parse_qs(parsed.query)
            indicators = _split_csv(_first(params, "indicators"))
            if not indicators:
                self._send_error(
                    HTTPStatus.BAD_REQUEST,
                    "Missing required query parameter: indicators",
                )
                return

            attributes = _split_csv(_first(params, "attributes")) or "price"
            period = _first(params, "period")
            start = _first(params, "start")
            end = _first(params, "end")

            try:
                data = fetch_data_as_dict(
                    indicators=indicators,
                    attributes=attributes,
                    period=period,
                    start=start,
                    end=end,
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return

            self._send_json(HTTPStatus.OK, {"data": data})
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Not Found")


def _first(params: dict[str, Iterable[str]], key: str) -> str | None:
    """Return the first query parameter value for the given key."""
    values = params.get(key)
    if not values:
        return None
    return next(iter(values), None)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the HTTP server on the provided host and port."""
    server = ThreadingHTTPServer((host, port), PySFTRequestHandler)
    print(f"PySFT HTTP server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
