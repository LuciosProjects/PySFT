import pysft

from testIndicators import indicatorsDB

if __name__ == "__main__":
    indicators = indicatorsDB.TASE
    # indicators = indicatorsDB.PORTFOLIO

    # quote = pysft.lib.fetchData(indicators, start="2025-07-01", end="2025-08-01")

    # Simple single indicator fetch (should only give current price)
    # quote = pysft.lib.fetchData(indicators[0])

    # Simple multiple indicators fetch (should only give current prices)
    # quote = pysft.lib.fetchData(indicators)

    # Historical data fetch
    # quote = pysft.lib.fetchData(indicators, start="2024-01-01", end="2024-06-30", interval="1d")

    # All together fetch
    # quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], period="1m")

    # All together fetch for today's date only
    # quote = pysft.lib.fetchData('5138094', attributes=["all"], start="2024-01-01", end="2026-01-03") # MTF
    # quote = pysft.lib.fetchData('1144633', attributes=["all"], start="2025-08-01", end="2025-08-15") # ETF
    # quote = pysft.lib.fetchData('1186063', attributes=["all"], start="2025-08-01", end="2025-08-15") # Internationally traded ETF
    # quote = pysft.lib.fetchData(['1081124', '604611'], attributes=["all"], start="2025-08-01", end="2025-08-15") # STOCKS
    quote = pysft.lib.fetchData('629014', attributes=["all"], start="2025-08-01", end="2025-08-15") # STOCKS

    # quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], start="2025-07-01", end="2025-08-01")