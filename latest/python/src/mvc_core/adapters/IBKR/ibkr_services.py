from ib_insync import IB, ContFuture, util

import pandas as pd
import datetime
import random

from mvc_app.jobs import JobConfig, get_backtest_view
from mvc_core.performances.trades_reconstruction import build_trades_dataframe
from mvc_core.adapters.db_connection.postgres_connection import get_postgres

from dotenv import dotenv_values

IBKR_TO_DB_NAME = {
    "KC": "arabica",
    "SB": "sb11",
    "RC": "robusta",
}


def get_cont_contract(asset: str):
    if asset == "KC":
        return ContFuture(symbol="KC", exchange="NYBOT")
    elif asset == "SB":
        return ContFuture(symbol="SB", exchange="NYBOT")
    elif asset == "RC":
        return ContFuture(symbol="D", exchange="ICEEUSOFT")
    else:
        raise ValueError(f"Unknown asset: {asset}")


def fetch_daily_history(ib: IB, asset: str, duration: str = "30 D", barSizeSetting: str = "1 day"):
    contract = get_cont_contract(asset)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting=barSizeSetting,
        whatToShow="TRADES",
        useRTH=False,
        formatDate=1,
    )
    # On a reqHistoricalData timeout ib_insync returns no bars and util.df()
    # gives None: return an empty frame so callers only have to check .empty.
    return util.df(bars) if bars else pd.DataFrame()


def to_db_str(value: float) -> str:
    """Convert a float price into str (cents)."""
    return str(int(round(value * 100)))


def upsert_futures_row(name: str, date: str, open_: str, high: str, low: str, close: str, volume: str):
    db = get_postgres()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    existing = db.select_from_query(
        "SELECT id FROM public.data_market_intelligence_futures WHERE name = %s AND date = %s LIMIT 1",
        (name, date),
    )

    if existing.empty:
        query = """
            INSERT INTO public.data_market_intelligence_futures
                (name, date, open, high, low, close, volume, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        db.execute_write_querry(query, (name, date, open_, high, low, close, volume, now, now))
    else:
        query = """
            UPDATE public.data_market_intelligence_futures
            SET open = %s, high = %s, low = %s, close = %s, volume = %s, updated_at = %s
            WHERE name = %s AND date = %s
        """
        db.execute_write_querry(query, (open_, high, low, close, volume, now, name, date))


def upsert_trade_row(name: str, date: str, trade: int):
    db = get_postgres()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    existing = db.select_from_query(
        "SELECT id FROM public.data_market_intelligence_trades WHERE name = %s AND date = %s LIMIT 1",
        (name, date),
    )

    if existing.empty:
        query = """
            INSERT INTO public.data_market_intelligence_trades
                (name, date, trade, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        db.execute_write_querry(query, (name, date, trade, now, now))
    else:
        query = """
            UPDATE public.data_market_intelligence_trades
            SET trade = %s, updated_at = %s
            WHERE name = %s AND date = %s
        """
        db.execute_write_querry(query, (trade, now, name, date))



def delete_trades_not_in(name: str, dates: list):
    """
    Delete the trades of `name` whose date isn't in `dates` (the latest run's
    trades): a trade that moved to another date or disappeared would otherwise
    stay in the table next to the new ones.
    """
    if not dates:
        return
    db = get_postgres()
    db.execute_write_querry(
        "DELETE FROM public.data_market_intelligence_trades WHERE name = %s AND NOT (date = ANY(%s::timestamp[]))",
        (name, list(dates)),
    )


def fetch_and_upsert_trades(profile: str):
    """
    Rebuild trades of a profile and upsert them (name / date / +1|-1) into the database.
    Existing rows (same name + date) are updated, new ones inserted, and the
    profile's rows on other dates deleted.
    """
    res = get_backtest_view(JobConfig(profile_name=profile))
    decisions = res["oos"].get("decisions", [])
    trades_df = build_trades_dataframe(decisions, include_open_positions=True)

    if trades_df.empty:
        print(f"Warning: No trades for {profile}. Skipping.")
        return

    dates = []
    for _, row in trades_df.iterrows():
        date = pd.to_datetime(row["entry_date"]).strftime("%Y-%m-%d %H:%M:%S")
        trade = 1 if row["side"] == "LONG" else -1
        upsert_trade_row(name=profile, date=date, trade=trade)
        dates.append(date)
        print(f"{profile} -> upserted {date}: trade={trade}")

    delete_trades_not_in(profile, dates)
    print(f"Done. {len(trades_df)} trade(s) upserted for {profile}.")


def upsert_trades_csv(name: str, csv_path: str):
    """
    Upsert the trades of a trades CSV (date / +1|-1) into the database under `name`,
    for strategies that aren't walk-forward profiles (Fusion), and delete the
    rows of `name` on dates the CSV no longer has.
    """
    trades_df = pd.read_csv(csv_path)

    dates = []
    for _, row in trades_df.iterrows():
        date = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M:%S")
        trade = int(row["trade"])
        upsert_trade_row(name=name, date=date, trade=trade)
        dates.append(date)
        print(f"{name} -> upserted {date}: trade={trade}")

    delete_trades_not_in(name, dates)
    print(f"Done. {len(trades_df)} trade(s) upserted for {name}.")

### LEGACY VERSION

# def fetch_and_upsert():
#     """
#     Connect to IBKR, fetch the last 2 days of daily bars for each asset,
#     and upsert T-1 (refresh yesterday) + T (today) into the database.
#     """
#     config = dotenv_values("/tmp/secrets/.env")

#     ib = IB()
#     ib.connect(config['IBGATEWAY_HOST'],config['IBGATEWAY_PORT'],clientId=1)

#     date_today = datetime.datetime.now().date()
#     date_yesterday = date_today - datetime.timedelta(days=1)
#     results = {}

#     for asset in ["KC", "SB", "RC"]:
#         db_name = IBKR_TO_DB_NAME[asset]

#         df = fetch_daily_history(ib, asset, duration="2 D")
#         df.index = pd.to_datetime(df["date"]).dt.date

#         # Upsert T-1 (yesterday) — refresh in case it was incomplete
#         if date_yesterday in df.index:
#             row_y = df.loc[df.index == date_yesterday].iloc[0]
#             upsert_futures_row(
#                 name=db_name,
#                 date=str(date_yesterday),
#                 open_=to_db_str(row_y["open"]),
#                 high=to_db_str(row_y["high"]),
#                 low=to_db_str(row_y["low"]),
#                 close=to_db_str(row_y["close"]),
#                 volume=str(int(row_y["volume"])),
#             )
#             print(f"{asset} ({db_name}) -> upserted T-1 ({date_yesterday}): "
#                   f"O={row_y['open']:.2f} H={row_y['high']:.2f} L={row_y['low']:.2f} C={row_y['close']:.2f} V={int(row_y['volume'])}")

#         # Upsert T (today)
#         if date_today not in df.index:
#             print(f"Warning: No data for {asset} ({db_name}) on {date_today}. Skipping.")
#             continue

#         row = df.loc[df.index == date_today].iloc[0]
#         results[asset] = row

#         upsert_futures_row(
#             name=db_name,
#             date=str(date_today),
#             open_=to_db_str(row["open"]),
#             high=to_db_str(row["high"]),
#             low=to_db_str(row["low"]),
#             close=to_db_str(row["close"]),
#             volume=str(int(row["volume"])),
#         )
#         print(f"{asset} ({db_name}) -> upserted T ({date_today}): "
#               f"O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} V={int(row['volume'])}")

#     ib.disconnect()

#     if not results:
#         print(f"No data fetched for any asset on {date_today}.")
#     else:
#         print(f"Done. {len(results)} asset(s) upserted for {date_today}.")


def fetch_and_upsert(nb_periods: int = 2):
    """
    Connect to IBKR, fetch the last nb_periods days of daily bars for each asset,
    and upsert all retrieved rows into the database.

    Picks a random clientId in [10, 31] on each call. ib_insync rejects a
    second concurrent connection that shares a clientId, and IB Gateway
    caps the API slots at 32 by default, so we stay well below. Random
    (rather than a per-script fixed value) also covers the case where
    the same script gets fired twice in parallel — which is exactly what
    we suspect happens at 17:30 with the double trigger.
    """
    config = dotenv_values("/tmp/secrets/.env")

    ib = IB()
    ib.connect(config['IBGATEWAY_HOST'], config['IBGATEWAY_PORT'], clientId=random.randint(10, 31))

    total_upserted = 0

    for asset in ["KC", "SB", "RC"]:
        db_name = IBKR_TO_DB_NAME[asset]

        df = fetch_daily_history(ib, asset, duration=f"{nb_periods} D")

        # Skipping is safe: every run re-fetches the last nb_periods days,
        # so the next one fills the gap.
        if df.empty:
            print(f"Warning: No data fetched for {asset} ({db_name}). Skipping.")
            continue

        df.index = pd.to_datetime(df["date"]).dt.date

        for date, row in df.iterrows():
            upsert_futures_row(
                name=db_name,
                date=str(date),
                open_=to_db_str(row["open"]),
                high=to_db_str(row["high"]),
                low=to_db_str(row["low"]),
                close=to_db_str(row["close"]),
                volume=str(int(row["volume"])),
            )
            print(f"{asset} ({db_name}) -> upserted {date}: "
                  f"O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} V={int(row['volume'])}")
            total_upserted += 1

    ib.disconnect()

    if total_upserted == 0:
        print("No data upserted.")
    else:
        print(f"Done. {total_upserted} row(s) upserted across all assets.")
