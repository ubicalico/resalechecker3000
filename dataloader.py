"""
 __  __     __     ______     __  __     ______     __    __     ______    
/\ \_\ \   /\ \   /\  ___\   /\ \_\ \   /\  __ \   /\ "-./  \   /\  __ \   
\ \  __ \  \ \ \  \ \___  \  \ \  __ \  \ \  __ \  \ \ \-./\ \  \ \ \/\ \  
 \ \_\ \_\  \ \_\  \/\_____\  \ \_\ \_\  \ \_\ \_\  \ \_\ \ \_\  \ \_____\ 
  \/_/\/_/   \/_/   \/_____/   \/_/\/_/   \/_/\/_/   \/_/  \/_/   \/_____/ 
                                                                           
"""

from pathlib import Path #os lib keep giving wrong cwd so pathlib it is lol

import pandas as pd
import requests
from sqlalchemy import create_engine, inspect, text

DATASET_URL = "https://data.gov.sg/api/action/datastore_search"
RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
PAGE_SIZE = 10000

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hdb_resale.db"
TABLE_NAME = "resale_transactions"


def fetch_all_records():
    """Page through the datastore_search endpoint until every record is fetched."""
    records = []
    offset = 0
    total = None
    while total is None or offset < total:
        resp = requests.get(
            DATASET_URL,
            params={"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()["result"]
        total = result["total"]
        batch = result["records"]
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
        print(f"  fetched {offset:,} / {total:,} records", flush=True)
    return records


def build_dataframe(records):
    """Clean and enrich the raw API records with pandas."""
    df = pd.DataFrame(records).drop(columns=["_id"])

    df["floor_area_sqm"] = pd.to_numeric(df["floor_area_sqm"], errors="coerce")
    df["resale_price"] = pd.to_numeric(df["resale_price"], errors="coerce")
    df["lease_commence_date"] = pd.to_numeric(df["lease_commence_date"], errors="coerce").astype("Int64")

    # "61 years 04 months" -> 61.33 (months part is optional in the source data)
    lease = df["remaining_lease"].str.extract(r"(?P<y>\d+)\s*years?(?:\s*(?P<m>\d+)\s*months?)?")
    df["remaining_lease_years"] = (
        pd.to_numeric(lease["y"], errors="coerce")
        + pd.to_numeric(lease["m"], errors="coerce").fillna(0) / 12
    ).round(2)

    df["price_per_sqm"] = (df["resale_price"] / df["floor_area_sqm"]).round(2)

    return df.sort_values("month").reset_index(drop=True)


def load_data(engine):
    """Fetch from the API and write the cleaned data into SQLite via SQLAlchemy."""
    print("Downloading HDB resale data from data.gov.sg ...", flush=True)
    df = build_dataframe(fetch_all_records())
    df.to_sql(TABLE_NAME, engine, if_exists="replace", index=False, chunksize=5000)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_month ON {TABLE_NAME} (month)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_town ON {TABLE_NAME} (town)"))
    print(f"Loaded {len(df):,} rows into {DB_PATH.name}", flush=True)


def ensure_data(engine):
    """Load the database on first run; do nothing if it is already populated."""
    if inspect(engine).has_table(TABLE_NAME):
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
        if count:
            print(f"Database ready ({count:,} rows). Run 'python dataloader.py' to refresh it.")
            return
    load_data(engine)


if __name__ == "__main__":
    # Running this script directly always re-downloads the latest data.
    load_data(create_engine(f"sqlite:///{DB_PATH}"))
