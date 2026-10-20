import requests
import json
import gzip
import sqlite3
from datetime import date
import time
from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)


class Fundamental:
    def __init__(self):
        self.token = os.getenv('token')
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }

    def db_connection(self):
        conn=sqlite3.connect('tradApp.db')
        cursor=conn.cursor()
        return conn,cursor


    ## use to fetch isin and company name and Trading symbol
    def get_company(self):
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        response=requests.get(url)
        instruments=json.loads(gzip.decompress(response.content))

        stocks=[
            {"Name":item.get("name",'none'),
            "ISIN":item.get("isin",'none'),
            "Symbol":item.get("trading_symbol",'none')
            }
            for item in instruments
            if item.get("segment") == "NSE_EQ"
            and item.get("instrument_type") == "EQ"
            and item.get("exchange") == "NSE"
        ]

        conn, cursor = self.db_connection()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    isin TEXT PRIMARY KEY,
                    name TEXT,
                    symbol TEXT
                )
            """)

            ## will check the already present the stocks 
            cursor.execute("""select isin from stocks""")
            existing_isins = {row[0] for row in cursor.fetchall()}

            ## new stocks will be shortlisted and add in the database
            new_stocks = [
            stock for stock in stocks
            if stock["ISIN"] not in existing_isins
                  ]

            
            cursor.executemany("""
                INSERT OR IGNORE INTO stocks (isin, name, symbol)
                VALUES (:ISIN, :Name, :Symbol)
            """, new_stocks)

            conn.commit()

            print(f'Total new stocks fetched: {len(new_stocks)}')
        finally:
            conn.close()


    ## will use to fetch company sector and market cap
    def get_profile(self):
        print('********** Starting Getting Profile of the Company ************')

        conn,cursor = self.db_connection()
        record_date = date.today().isoformat()
        
        try:
            cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_details (
                        isin TEXT NOT NULL,
                        sector TEXT,
                        market_cap REAL,
                        record_date TEXT NOT NULL,
                        PRIMARY KEY (isin, record_date)
                    )
                """)
           
            cursor.execute('''
                select isin from stocks
            ''')
           
            isins=[row[0] for row in cursor.fetchall() if row[0]]
        

            for isin in isins: 
                url = f'https://api.upstox.com/v2/fundamentals/{isin}/profile'
                response = requests.get(url, headers=self.headers,timeout=60)
                data=response.json()
                if response.status_code != 200:
                    raise Exception(f"Failed to fetch profile for ISIN {isin}: {response.status_code} - {response.text}")
                else:
                    print(f"Successfully fetched profile for ISIN {isin}")
                    listData={
                        'isin':isin,
                        'sector':data.get('data',{}).get('sector','none'),
                        'market_cap':data.get('data',{}).get('sector_market_cap_inr',{}).get('value','none')
                    }
                    print(listData)
                    cursor.execute("""
                        INSERT INTO company_details (
                            isin, sector, market_cap, record_date
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(isin, record_date) DO UPDATE SET
                            sector = excluded.sector,
                            market_cap = excluded.market_cap
                    """, (
                        listData['isin'],
                        listData['sector'],
                        listData['market_cap'],
                        record_date
                ))
                conn.commit()
                print(f'data store for isin {listData['isin']}')
                
                time.sleep(1)

        finally:
            conn.close()

fund=Fundamental()
fund.get_profile()
# fund.get_company()
