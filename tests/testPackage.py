import pysft

from testIndicators import indicatorsDB

if __name__ == "__main__":
    # indicators = indicatorsDB.PORTFOLIO
    indicators = ["AAPL", "MSFT", "GOOG", "TSLA", "NVDA"] 

    # quote = pysft.lib.fetchData(indicators, start="2025-07-01", end="2025-08-01")

    # Simple single indicator fetch (should only give current price)
    quote = pysft.lib.fetchData("AAPL")

    # Simple multiple indicators fetch (should only give current prices)
    quote = pysft.lib.fetchData(indicators)

    # Historical data fetch
    quote = pysft.lib.fetchData(indicators, start="2024-01-01", end="2024-06-30", interval="1d")

    # All together fetch
    quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], period="1m")

    quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], start="2024-05-01", end="2024-06-30", interval="1d")