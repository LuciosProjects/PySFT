import pysft

from testIndicators import indicatorsDB

if __name__ == "__main__":
    indicators = indicatorsDB.PORTFOLIO

    # quote = pysft.lib.fetchData(indicators, start="2025-07-01", end="2025-08-01")
    quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], period="1m")