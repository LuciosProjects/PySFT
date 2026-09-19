"""Global safety fixtures for the PySFT test suite."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from tests.support.environment import PySFTTestEnvironment, RepositoryDatabaseGuard
from tests.support.scenarios import DeterministicProviderGateway

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run tests that contact real external providers",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="live provider tests require --run-live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session", autouse=True)
def repository_database_guard() -> Any:
    guard = RepositoryDatabaseGuard(REPOSITORY_ROOT)
    yield guard
    guard.assert_unchanged()


@pytest.fixture(autouse=True)
def block_external_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail deterministic tests immediately on an external socket connection."""

    if request.node.get_closest_marker("live") is not None:
        return

    original_connect = socket.socket.connect

    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        if isinstance(address, tuple):
            host = str(address[0])
            if host not in LOOPBACK_HOSTS:
                raise AssertionError(
                    f"External network access is forbidden in deterministic tests: {host}"
                )
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def pysft_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    environment = PySFTTestEnvironment(
        tmp_path / "pysft-test.db", monkeypatch, REPOSITORY_ROOT
    ).start()
    try:
        yield environment
    finally:
        environment.close()


@pytest.fixture
def provider_gateway(monkeypatch: pytest.MonkeyPatch) -> DeterministicProviderGateway:
    return DeterministicProviderGateway().install(monkeypatch)
