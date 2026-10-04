"""Public API and output-contract tests."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from pysft.core.io import _parse_attributes
from pysft.lib import (
    fetch_data,
    fetch_data_as_df,
    fetch_data_as_dict,
    fetch_data_as_json,
    fetchData,
    fetchData_as_df,
)
from tests.support.scenarios import YFinanceScenarioFactory

pytestmark = [pytest.mark.e2e]


class TestPublicApi:
    def test_aliases_return_the_same_dictionary_contract(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        camel_case = fetchData("AAPL", mode="price")
        snake_case = fetch_data("AAPL", mode="price")
        explicit_dict = fetch_data_as_dict("AAPL", mode="price")

        assert camel_case == snake_case == explicit_dict
        assert list(camel_case) == ["AAPL"]
        assert camel_case["AAPL"]["price"] == [100.0]

    def test_json_and_dataframe_outputs_preserve_values(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        dictionary = fetch_data_as_dict("AAPL", mode="price")
        json_output = json.loads(fetch_data_as_json("AAPL", mode="price"))
        camel_frame = fetchData_as_df("AAPL", mode="price")
        snake_frame = fetch_data_as_df("AAPL", mode="price")

        assert json_output == dictionary
        pd.testing.assert_frame_equal(camel_frame, snake_frame)
        assert camel_frame.loc[pd.Timestamp("2024-01-02"), ("AAPL", "price")] == 100.0

    @pytest.mark.parametrize("mode", ["price", "info", "all"])
    def test_supported_modes_complete_through_public_api(
        self, pysft_env, provider_gateway, mode
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        result = fetch_data("AAPL", mode=mode)

        assert result["AAPL"]
        if mode == "price":
            assert "price" in result["AAPL"]
            assert "name" not in result["AAPL"]
        elif mode == "info":
            assert result["AAPL"]["name"] == ["AAPL Incorporated"]
            assert "price" not in result["AAPL"]
        else:
            assert result["AAPL"]["price"] == [100.0]
            assert result["AAPL"]["name"] == ["AAPL Incorporated"]

    def test_string_lists_are_normalized_and_duplicates_are_stable(
        self, pysft_env, provider_gateway
    ):
        provider_gateway.add(
            YFinanceScenarioFactory.equity("AAPL"),
            YFinanceScenarioFactory.equity("MSFT", price=200.0),
        )

        result = fetch_data(" aapl, MSFT, AAPL ", mode="price")

        assert list(result) == ["AAPL", "MSFT"]

    @pytest.mark.parametrize(
        ("mode", "attributes"),
        [
            ("price", ["name"]),
            ("info", ["close"]),
            ("all", ["vol", "dates"]),
            ("price", "info"),
            ("info", "all"),
        ],
    )
    def test_explicit_attributes_override_mode_and_aliases_are_canonical(
        self, pysft_env, provider_gateway, mode, attributes
    ):
        provider_gateway.add(YFinanceScenarioFactory.equity())

        result = fetch_data("AAPL", attributes=attributes, mode=mode)["AAPL"]

        assert set(result) == {"dates", *_parse_attributes(attributes)}
        assert result["dates"] == ["2024-01-02"]
        if attributes == ["name"]:
            assert result["name"] == ["AAPL Incorporated"]
        elif attributes == ["close"]:
            assert result["last"] == [100.0]
        elif attributes == ["vol", "dates"]:
            assert result["volume"] == [1000]
        elif attributes == "info":
            assert result["name"] == ["AAPL Incorporated"]
            assert "price" not in result
        else:
            assert result["name"] == ["AAPL Incorporated"]
            assert result["price"] == [100.0]

    def test_python_aliases_keep_the_explicit_selection_on_cache_hits(
        self, pysft_env, provider_gateway
    ):
        today = pd.Timestamp.now().date().isoformat()
        provider_gateway.add(YFinanceScenarioFactory.equity(dates=(today,)))

        camel_case = fetchData("AAPL", attributes="name", mode="price")
        snake_case = fetch_data("AAPL", attributes="name", mode="all")
        explicit_dict = fetch_data_as_dict(
            "AAPL", attributes="name", mode="info"
        )
        json_output = json.loads(
            fetch_data_as_json("AAPL", attributes="name", mode="price")
        )
        camel_frame = fetchData_as_df(
            "AAPL", attributes="name", mode="price"
        )
        snake_frame = fetch_data_as_df(
            "AAPL", attributes="name", mode="all"
        )

        expected = {"AAPL": {"dates": [today], "name": ["AAPL Incorporated"]}}
        assert camel_case == snake_case == explicit_dict == json_output == expected
        pd.testing.assert_frame_equal(camel_frame, snake_frame)
        assert list(camel_frame.columns) == [("AAPL", "name")]
        assert provider_gateway.calls["AAPL"] == 1


class TestPublicInputValidation:
    @pytest.mark.parametrize("mode", ["", "PRICE", "unsupported"])
    def test_invalid_mode_fails_before_provider_work(
        self, pysft_env, provider_gateway, mode
    ):
        with pytest.raises(ValueError, match="Unsupported mode"):
            fetch_data("AAPL", mode=mode)
        assert provider_gateway.routes == []

    def test_invalid_attribute_fails_before_provider_work(
        self, pysft_env, provider_gateway
    ):
        with pytest.raises(ValueError, match="Unsupported attribute"):
            fetch_data("AAPL", attributes=["not-a-field"])
        assert provider_gateway.routes == []

    def test_period_and_explicit_range_are_mutually_exclusive(
        self, pysft_env, provider_gateway
    ):
        with pytest.raises(ValueError, match="either 'period' OR"):
            fetch_data("AAPL", period="1m", start="2024-01-01")

    def test_reversed_range_is_rejected(self, pysft_env, provider_gateway):
        with pytest.raises(ValueError, match="Start date"):
            fetch_data("AAPL", start="2024-02-01", end="2024-01-01")

    def test_empty_indicator_input_returns_empty_result(
        self, pysft_env, provider_gateway
    ):
        assert fetch_data([], mode="price") == {}
