import requests

sessionHeaders = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

def fetch_page_html(url: str, timeout: int) -> str:
    response = requests.get(url, headers=sessionHeaders, timeout=timeout)

    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch page. Status code: {response.status_code}")

if __name__ == "__main__":
    filename = "tase_5138094_historical_p19_including_daterange_html.txt"
    filepath = "./debug/" + filename

    # url = "https://finance.themarker.com/stock/1104249"
    # url = "https://maya.tase.co.il/he/funds/mutual-funds/5138094"
    url = "https://maya.tase.co.il/he/funds/mutual-funds/5138094/historical-data?period=4&fromDate=2000-01-01T21:00:00.000Z&toDate=2025-12-26T22:00:00.000Z&pageNumber=19"

    text = fetch_page_html(url, timeout=10)

    # dump to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)