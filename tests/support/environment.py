"""Isolated runtime objects used by the PySFT end-to-end tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import TracebackType
from typing import Any, Self
from urllib.request import urlopen

import pysft.core.fetcher_manager as fetcher_manager_module
from pysft.core import database
from pysft.http_api import PySFTRequestHandler


@dataclass(frozen=True)
class DatabaseFingerprint:
    """Content and metadata used to prove a repository DB was untouched."""

    digest: str
    size: int
    modified_ns: int

    @classmethod
    def capture(cls, path: Path) -> DatabaseFingerprint:
        stat = path.stat()
        return cls(
            sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns
        )


class RepositoryDatabaseGuard:
    """Snapshots tracked databases and asserts that tests never modify them."""

    RELATIVE_PATHS = (
        Path("src/pysft/data/pysft_cache.db"),
        Path("src/pysft/data/tase_security_list.db"),
    )

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.paths = tuple(
            (self.repository_root / path).resolve() for path in self.RELATIVE_PATHS
        )
        self.before = {path: DatabaseFingerprint.capture(path) for path in self.paths}

    def assert_unchanged(self) -> None:
        after = {path: DatabaseFingerprint.capture(path) for path in self.paths}
        assert after == self.before, "The test suite modified a repository database"


class PySFTTestEnvironment:
    """Owns one temporary SQLite database and its PySFT configuration."""

    def __init__(
        self, database_path: Path, monkeypatch: Any, repository_root: Path
    ) -> None:
        self.database_path = database_path.resolve()
        self.monkeypatch = monkeypatch
        self.repository_root = repository_root.resolve()
        self._started = False

    def start(self) -> PySFTTestEnvironment:
        protected = {
            (self.repository_root / relative).resolve()
            for relative in RepositoryDatabaseGuard.RELATIVE_PATHS
        }
        if (
            self.database_path in protected
            or self.repository_root in self.database_path.parents
        ):
            raise RuntimeError("Test database must be outside the repository")

        database.close_db()
        self.monkeypatch.setattr(database, "DB_PATH", str(self.database_path))
        self.monkeypatch.setattr(database, "DB_ENABLED", True)
        self.monkeypatch.setattr(fetcher_manager_module, "DB_ENABLED", True)
        self._started = True
        return self

    @property
    def manager(self) -> database.DatabaseManager:
        if not self._started:
            raise RuntimeError("Test environment has not been started")
        return database.get_db_manager()

    def scalar_row_count(self, indicator: str | None = None) -> int:
        return self._row_count("indicator_attributes", indicator)

    def price_row_count(self, indicator: str | None = None) -> int:
        return self._row_count("price_history", indicator)

    def expire_scalar_values(self, indicator: str) -> None:
        self.manager.connection.execute(
            "UPDATE indicator_attributes SET fetched_at = datetime('now', '-1 day') WHERE indicator = ?",
            (indicator,),
        )
        self.manager.connection.commit()

    def _row_count(self, table: str, indicator: str | None) -> int:
        if table not in {"indicator_attributes", "price_history"}:
            raise ValueError(f"Unsupported test table: {table}")
        query = f"SELECT COUNT(*) FROM {table}"
        params: tuple[str, ...] = ()
        if indicator is not None:
            query += " WHERE indicator = ?"
            params = (indicator,)
        row = self.manager.connection.execute(query, params).fetchone()
        return int(row[0])

    def close(self) -> None:
        database.close_db()
        self._started = False


class HttpServerHarness:
    """Runs the standard-library HTTP API on an ephemeral loopback port."""

    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PySFTRequestHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> Self:
        self.thread.start()
        return self

    def get_json(self, path: str) -> tuple[int, dict[str, Any]]:
        with urlopen(f"{self.base_url}{path}", timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
