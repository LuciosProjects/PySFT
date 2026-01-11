import requests
import json

sessionHeaders = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0"
            }

def fetch_tase_page_json(url: str, indicator: str, payload: dict, timeout: int = 30):

    response = requests.post(url, headers=sessionHeaders, json=payload, timeout=timeout)
    response.raise_for_status()

    return response.json()

if __name__ == "__main__":
    # indicator = "5138094"  # Example TASE fund indicator
    # url = f"https://maya.tase.co.il/api/v1/funds/mutual/{indicator}/history"

    # payload = {
    #     "pageSize": 20,
    #     "pageNumber": 1,
    #     "period": 4,
    #     # "fromDate": "2000-01-01T00:00:00.000Z",
    #     "fromDate": "2025-12-25T00:00:00.000Z",
    #     "toDate": "2025-12-27T22:00:00.000Z"
    # }

    indicator = "1104249"  # Example TASE stock indicator
    url = f"https://maya.tase.co.il/api/v1/security/{indicator}/historyeod"

    payload = {
        "pType": "7",
        # "dFrom": "2000-01-01",
        # "dTo": "2025-12-27",
        "TotalRec": 1,
        "pageNum": 1,
        "oId": indicator.zfill(8),
        "lang": "0"
    }

    filename = f"{indicator}_tase_historical_data.json"
    filepath = "./debug/" + filename

    json_data = fetch_tase_page_json(url, indicator, payload, timeout=10)

    # dump to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(json.dumps(json_data))