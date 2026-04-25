from pathlib import Path
import sys

# tests/testPackage.py -> PySFT/src
pysft_src = Path(__file__).resolve().parents[1] / "src"
if not (pysft_src / "pysft").is_dir():
    raise RuntimeError(f"Cannot find pysft package at: {pysft_src}")

sys.path.insert(0, str(pysft_src))

import pysft

pysft.core.database.resetDatabase()

from testIndicators import indicatorsDB

if __name__ == "__main__":
    # indicators = indicatorsDB.TASE
    indicators = indicatorsDB.PORTFOLIO
    # indicators = indicatorsDB.getShuffeledPortfolio("YF400_TASE100")

    # quote = pysft.lib.fetchData(indicators, start="2025-07-01", end="2025-08-01")

    # Simple single indicator fetch (should only give current price)
    # quote = pysft.lib.fetchData(indicators[0])

    # Simple multiple indicators fetch (should only give current prices)
    # quote = pysft.lib.fetchData(indicators)

    # Historical data fetch
    # quote = pysft.lib.fetchData(indicators, start="2024-01-01", end="2024-06-30", interval="1d")

    # All together fetch
    # quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], period="1m")

    # quote = pysft.lib.fetchData(indicators, attributes=["name", "price", "high", "low", "open", "volume"], start="2025-07-01", end="2025-08-01")

    # today_quote = pysft.lib.fetchData(indicators, attributes=["all"])
    # historical_quote    = pysft.lib.fetchData("AAPL", attributes=["all"], start="2025-07-01", end="2026-03-02")
    # today_quote         = pysft.lib.fetchData("AAPL", attributes=["all"])
    # historical_quote    = pysft.lib.fetchData("AAPL", attributes=["all"], start="2025-09-01", end="2025-09-10")
    # historical_quote    = pysft.lib.fetchData("AAPL", attributes=["all"], start="2025-08-01", end="2025-11-01")
    # historical_quote = pysft.lib.fetchData("AAPL", attributes=["all"], start="2025-07-10", end="2025-07-25")
    # result = pysft.lib.fetchData(["MSFT", "AAPL"], attributes=["price", "volume", "exchange"], period="1m")
    # result = pysft.lib.fetchData(["5138094"], attributes=["price", "volume", "exchange", "currency"], period="1m")

    today_quote = pysft.lib.fetchData(["1144633"], attributes=["all"])

    ...