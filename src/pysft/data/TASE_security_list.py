import datetime
import sqlite3
import requests

from pysft.core.tase_specific_utils import MAYA_TASE_URLS, TASE_DATAHUB_API_HEADERS, TASE_CALENDAR
import pysft.core.utilities as utils
import pysft.core.constants as const

first_date = datetime.date(2008, 1, 1)
print(f"TASE_secutiry_list.py: first_date - {first_date}")
last_date = datetime.date.today()
print(f"TASE_secutiry_list.py: last_date - {last_date}")

trading_days = TASE_CALENDAR.sessions_in_range(first_date, last_date)

def initialize_security_list_db() -> sqlite3.Cursor:
    """
    Initialize the SQLite database for storing TASE security lists.
    """

    conn = sqlite3.connect('src/pysft/data/tase_security_list.db')
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_list (
            indicator TEXT PRIMARY KEY,
            securityId INTEGER,
            securityFullTypeCode TEXT,
            isin TEXT,
            symbol TEXT,
            companySuperSector TEXT,
            companySector TEXT,
            companySubSector TEXT,
            securityIsIncludedInContinuousIndices TEXT,
            corporateId TEXT,
            issuerId INTEGER,
            companyName TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS db_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR REPLACE INTO db_metadata (key, value, key, value) VALUES (?, ?, ?, ?)", 
                   ("last_updated", datetime.datetime.now().isoformat(),"total_securities", 0))
    
    conn.commit()
    # conn.close()

    return cursor

def create_TASE_security_list():
    cursor = initialize_security_list_db()
    
    total_securities = 0
    for date in trading_days:
        print(f"Fetching security list for date: {date.strftime('%d/%m/%Y')}")
        url = MAYA_TASE_URLS.TRADED_SECURITIES_LISTING_API(date.year, date.month, date.day)

        for attempt in range(const.MAX_ATTEMPTS):
            try:
                # url = MAYA_TASE_URLS.TRADED_SECURITIES_LISTING_API(target_date.year, target_date.month, target_date.day)
                response = requests.get(url,
                                        headers=TASE_DATAHUB_API_HEADERS, 
                                        timeout=const.TASE_HTML_FETCH_TIMEOUT.seconds())
                response.raise_for_status()

                sList = response.json()['tradeSecuritiesList']
                if sList['total'] > 0:
                    for item in sList['result']:
                        indicator = str(item['securityId'])

                        if cursor.execute("SELECT 1 FROM security_list WHERE indicator = ?", (indicator,)).fetchone():
                            continue  # Skip existing entries
                        else:
                            total_securities += 1

                        cursor.execute('''
                            INSERT OR REPLACE INTO security_list (
                                indicator,
                                securityId,
                                securityFullTypeCode,
                                isin,
                                symbol,
                                companySuperSector,
                                companySector,
                                companySubSector,
                                securityIsIncludedInContinuousIndices,
                                corporateId,
                                issuerId,
                                companyName
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        ''', ( 
                            indicator,
                            item.get('securityId'),
                            item.get('securityFullTypeCode'),
                            item.get('isin'),
                            item.get('symbol'),
                            item.get('companySuperSector'),
                            item.get('companySector'),
                            item.get('companySubSector'),
                            str(item.get('securityIsIncludedInContinuousIndices')),
                            item.get('corporateId'),
                            item.get('issuerId'),
                            item.get('companyName')
                        ))

                break # Successful fetch, exit trial loop
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1} failed: {e}")
        utils.random_delay(0.5, 1.0)
    
    cursor.execute("INSERT OR REPLACE INTO db_metadata (key, value, key, value) VALUES (?, ?, ?, ?)", 
                   ("last_updated", datetime.datetime.now().isoformat(), "total_securities", total_securities))

    cursor.connection.commit()
    cursor.connection.close()

if __name__ == "__main__":
    create_TASE_security_list()