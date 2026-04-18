import sys
from pathlib import Path

from requests.sessions import Session
import json
import time, random

# tests/testPackage.py -> PySFT/src
pysft_src = Path(__file__).resolve().parents[1] / "src"
if not (pysft_src / "pysft").is_dir():
    raise RuntimeError(f"Cannot find pysft package at: {pysft_src}")

sys.path.insert(0, str(pysft_src))

import pysft.core.constants as const
import pysft.core.tase_specific_utils as tase_utils

def test_TASE_Fund_Expo(indicator: str, quote_type: str, session: Session) -> list[dict]:
    assets_url = f"https://maya.tase.co.il/api/v1/funds/{indicator}/assets"

    if quote_type == "MTF":
        maya_tase_url = f"https://maya.tase.co.il/en/funds/mutual-funds/{indicator}"
    elif quote_type == "ETF":
        maya_tase_url = f"https://market.tase.co.il/en/market_data/etf/{indicator}"

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US",
        "referer": maya_tase_url
    })

    holdings = []

    page = 1
    Done = False
    jsons: dict[str, dict] = {}
    while not Done:
        payload = {
            "pageNumber": page,
            "pageSize": 20
        }

        try:
            time.sleep(max([0.2, random.uniform(0.2, 0.5)])) 
            res = session.post(assets_url, json=payload, timeout=20)
            res.raise_for_status()
            
            content = res.json()

            if content.__len__() == 0:
                Done = True
            else:
                jsons["page_" + str(page)] = content
                page += 1
        except Exception as e:
            print(f"Error during POST request for page {page}: {e}")
            break


    for json_data in jsons.values():
        for row in json_data:
            holding = {
                    "id": row.get("id"),
                    "fundId": row.get("fundId"),
                    "managerId": row.get("managerId"),
                    "managerName": row.get("managerName"),
                    "assetId": row.get("assetId"),
                    "assetName": row.get("assetName"),
                    "assetType": row.get("assetTypeName"),
                    "fundPercentage": row.get("fundPercentage"),
                    "assetValue": row.get("nisValue"), # It's in plain NIS, but we can convert it to USD later if needed
                    "quantity": row.get("quantity"),
                    "tradePlace": row.get("tradePlace"),
                    "ticker": row.get("ticker")
            }
            holdings.append(holding)


    return holdings



if __name__ == "__main__":
    indicator = "5142088" # test cases: 5142088, 5111422, 1144633
    session = Session()

    url =  tase_utils.TASE_URLS.THEMARKER(indicator)
    quote_type = None

    for attempt in range(const.MAX_ATTEMPTS):
        try:
            head_response = session.head(url, allow_redirects=True, timeout=20)
            head_response.raise_for_status()
            real_url = head_response.url

            final_url = real_url
            url_segments = final_url.split('/')

            for segment in url_segments:
                if segment in const.THEMARKER_QUOTE_TYPES:
                    quote_type = segment.upper()
                    break

            break # Successful HEAD request, exit loop
        except Exception as e:
            if attempt == const.MAX_ATTEMPTS - 1:
                print(f"Failed to get real URL after {const.MAX_ATTEMPTS} attempts: {e}")
                exit(1)
    
    if quote_type == "MTF":
        maya_tase_url = f"https://maya.tase.co.il/en/funds/mutual-funds/{indicator}"
    elif quote_type == "ETF":
        maya_tase_url = f"https://market.tase.co.il/en/market_data/etf/{indicator}/major_data"

    try:
        res = session.get(maya_tase_url, allow_redirects=True, timeout=20)
    except Exception as e:
        print(f"Error during GET request: {e}")
        exit(1)


    if quote_type == "MTF":
        holdings = test_TASE_Fund_Expo(indicator, quote_type, session)

        for holding in holdings:
            print(holding)