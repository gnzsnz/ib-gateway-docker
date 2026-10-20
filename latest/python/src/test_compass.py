import json
import sys
from datetime import date as Date, timedelta

import httpx

from dotenv import dotenv_values

from dateutil import parser

from dotenv import dotenv_values

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


config = dotenv_values("/tmp/secrets/.env")

BASE_URL = config['COMPASS_URL']
HEADERS = {"access_token": config['COMPASS_TOKEN']}
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# Compass index to write allocations to, from .env: MXDSLSSI in production,
# DEEPCORETEST on staging. Required, with no default, so an environment
# missing it fails instead of silently writing to the production index.
INDEX = config['COMPASS_INDEX']

THEDEEPCORE_API_URL = config['THEDEEPCORE_URL']
THEDEEPCORE_ACCESS_TOKEN = config['THEDEEPCORE_TOKEN']


def _url(*parts: str) -> str:
    return "/".join([BASE_URL.rstrip("/"), "indexes", *parts])


class CutoffError(RuntimeError):
    """Compass refused an allocation because its date's cutoff has passed."""


def _raise_for_status(response: httpx.Response, expected: int) -> None:
    if response.status_code == expected:
        return
    msg = f"HTTP {response.status_code} – {response.text}"
    if response.status_code == httpx.codes.BAD_REQUEST and _is_cutoff(response):
        raise CutoffError(msg)
    raise RuntimeError(msg)


def _is_cutoff(response: httpx.Response) -> bool:
    try:
        details = response.json().get("detail", [])
    except ValueError:
        return False
    return isinstance(details, list) and any(
        isinstance(d, dict) and d.get("type") == "cutoff" for d in details
    )


def list_allocations(client: httpx.Client, index: str) -> list[dict]:
    """Return all allocation records for the given index, handling pagination."""
    url = _url(index, "allocations")
    records = []
    while url is not None:
        response = client.get(url)
        _raise_for_status(response, httpx.codes.OK)
        body = response.json()
        records.extend(body.get("data", []))
        url = body.get("next_url")
    return records


def post_allocation(
    client: httpx.Client,
    index: str,
    date: str,
    weights: dict[str, float],
) -> dict:
    """
    Create a new allocation.

    Parameters
    ----------
    date:
        ISO-8601 datetime string, e.g. "2024-01-15T00:00:00Z".
    weights:
        Mapping of underlying ticker → weight, e.g. {"AAPL": 0.5, "MSFT": 0.5}.
    """
    payload = {
        "date": date,
        "weights": [{"underlying": k, "value": v} for k, v in weights.items()],
    }
    response = client.post(
        _url(index, "allocations"),
        content=json.dumps(payload),
    )
    _raise_for_status(response, httpx.codes.CREATED)
    return response.json()["data"]


def delete_allocation(client: httpx.Client, index: str, date: str) -> None:
    """
    Delete the allocation for the given date.

    Parameters
    ----------
    date:
        ISO-8601 datetime string, e.g. "2024-01-15T00:00:00Z".
    """
    response = client.delete(_url(index, "allocations", date))
    _raise_for_status(response, httpx.codes.OK)


def parse_date(date: str):
    """
    Returns a date with format "YYYY-MM-DD"
    """
    date_str = parser.parse(date)
    y = date_str.strftime("%Y")
    m = date_str.strftime("%m")
    d = date_str.strftime("%d")
    return "-".join([y,m,d])


def get_trades(client: httpx.Client):
    """
    Get trades weights for sugar indices from TheDeepcore
    """
    response = client.get(
        THEDEEPCORE_API_URL,
        headers={'Content-Type':'application/json', 'Authorization': 'Bearer {}'.format(THEDEEPCORE_ACCESS_TOKEN)}
    )
    _raise_for_status(response, httpx.codes.OK)
    return response.json()["market_intelligence_trades"]


def send_slack_notification(message: str):
    # Staging's secret sets S3_PREFIX=staging/ (production has none): tag its
    # messages so they can't be mistaken for production's.
    environment = (config.get("S3_PREFIX") or "").strip("/")
    if environment:
        message = f"[{environment}] {message}"
    client = WebClient(token=config['SLACK_TOKEN'])
    try:
        response = client.chat_postMessage(
            channel=config['SLACK_CHANNEL'],
            text=message,
            username=config['SLACK_USERNAME']
        )
    except SlackApiError as exception:
        print(exception)


def next_weekday(day: Date) -> Date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


# Sentinels returned by post_latest_trade for the two "nothing to post" cases.
# RESULT_NO_TRADES means the trade list is empty (trade data not yet written for
# today — a retry is pertinent). RESULT_ALREADY_COVERED means the latest trade
# is already covered by an existing allocation (fully done — no retry needed).
RESULT_NO_TRADES = "no_trades"
RESULT_ALREADY_COVERED = "already_covered"


def post_latest_trade(client: httpx.Client, allocation_dates: list[str], trades: list[dict]):
    """
    Send the latest trade to Compass, unless an allocation already covers it.

    Compass only takes an allocation for date D until a cutoff early on D
    (07:15 New York), while the trade for D is computed in the afternoon of
    D. When D's cutoff has passed, the allocation goes to the next weekday
    whose cutoff hasn't, i.e. the first day the position can take effect.
    Older trades are already in Compass (or past their cutoff for good), so
    only the latest one is sent.

    Returns one of:
      - RESULT_NO_TRADES         when the trades list is empty (retry pertinent)
      - RESULT_ALREADY_COVERED   when an existing allocation already covers the
                                 latest trade (no retry needed)
      - the posted ISO date string when a new allocation was created
    """
    if not trades:
        print("No trades.")
        return RESULT_NO_TRADES

    latest = max(trades, key=lambda item: parse_date(item['date']))
    trade_date = parse_date(latest['date'])
    if any(d >= trade_date for d in allocation_dates):
        print(f"Trade of {trade_date} already allocated.")
        return RESULT_ALREADY_COVERED

    weights = {"MXSUGAFE": latest['trade']}
    day = Date.fromisoformat(trade_date)
    for _ in range(7):
        try:
            created = post_allocation(client, INDEX, f"{day.isoformat()}T00:00:00Z", weights)
            print(created)
            return day.isoformat()
        except CutoffError:
            print(f"Cutoff passed for {day.isoformat()}, trying the next weekday.")
            day = next_weekday(day)
    raise RuntimeError(f"No allocation date accepted for the trade of {trade_date}")


# Exit codes, read by app.py to decide whether to retry. EXIT_NOTHING_NEW is 10
# rather than 2 to avoid colliding with Python's standard exit code 2 (argparse
# errors, SystemExit(2) from vendored libs, interpreter flags like -W error):
# an unrelated SystemExit(2) must not be silently treated as "nothing new".
EXIT_POSTED = 0
EXIT_FAILED = 1
EXIT_NOTHING_NEW = 10


def main(retry: bool = False) -> int:
    # Retry runs are tagged in Slack so they're visibly distinguishable from the
    # first attempt. app.py decides whether to schedule a retry (based on this
    # script's exit code) and posts its own notice when it does.
    label = "[compass] (retry)" if retry else "[compass]"
    try:
        with httpx.Client(headers=HEADERS) as client:
            # 1. List existing allocations
            print("=== Listing allocations ===")
            allocations = list_allocations(client, INDEX)
            dates = [parse_date(alloc['date']) for alloc in allocations]

            # 2. Create the allocation of the latest trade
            print("=== Create allocations ===")
            posted = post_latest_trade(client, dates, get_trades(client))

            if posted == RESULT_NO_TRADES:
                send_slack_notification(f"✅ {label} Updated data successfully (nothing new)")
                return EXIT_NOTHING_NEW
            if posted == RESULT_ALREADY_COVERED:
                send_slack_notification(f"✅ {label} Updated data successfully (already covered)")
                return EXIT_POSTED
            send_slack_notification(f"✅ {label} Updated data successfully (allocation of {posted})")
            return EXIT_POSTED
    except Exception as e:
        import traceback
        traceback.print_exc()
        send_slack_notification(f"❌ {label} Failed to update data: {type(e).__name__}: {e}")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main(retry="--retry" in sys.argv[1:]))
