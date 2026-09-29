"""Focused tests for fetch-task payload handling."""

from __future__ import annotations

import pytest

from pysft.core.enums import E_FetchType
from pysft.core.fetch_task import fetchTask
from pysft.core.models import _YF_fetchReq_Container
from pysft.core.structures import indicatorRequest

pytestmark = [pytest.mark.unit]


def _raise_controlled_error(_payload: object) -> None:
    raise RuntimeError("controlled provider failure")


class TestSingleIndicatorTask:
    def test_success_returns_the_original_request(self) -> None:
        request = indicatorRequest("123456")
        task = fetchTask(E_FetchType.TASE, request)

        def succeed(payload: indicatorRequest) -> None:
            payload.success = True

        task.fetchFcn = succeed
        task.execute()

        assert task.get_results() is request
        assert request.success is True

    def test_failure_updates_the_original_request(self) -> None:
        request = indicatorRequest("123456")
        task = fetchTask(E_FetchType.TASE, request)
        task.fetchFcn = _raise_controlled_error

        task.execute()

        assert task.get_results() is request
        assert request.success is False
        assert request.message == "controlled provider failure"


class TestBatchedTask:
    def test_success_returns_the_container_requests(self) -> None:
        requests = [indicatorRequest("AAPL"), indicatorRequest("MSFT")]
        container = _YF_fetchReq_Container(requests)
        task = fetchTask(E_FetchType.YFINANCE, container)

        def succeed(payload: _YF_fetchReq_Container) -> None:
            for request in payload.requests:
                request.success = True

        task.fetchFcn = succeed
        task.execute()

        assert task.get_results() is requests
        assert all(request.success for request in requests)

    def test_failure_updates_every_container_request(self) -> None:
        requests = [indicatorRequest("AAPL"), indicatorRequest("MSFT")]
        container = _YF_fetchReq_Container(requests)
        task = fetchTask(E_FetchType.YFINANCE, container)
        task.fetchFcn = _raise_controlled_error

        task.execute()

        assert task.get_results() is requests
        assert all(not request.success for request in requests)
        assert all(
            request.message == "controlled provider failure"
            for request in requests
        )
