import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pandas.core.nanops")
warnings.filterwarnings("ignore", category=FutureWarning)

from mvc_app.view import export_profile_trades_csv
from mvc_core.adapters.db_connection.postgres_connection import PostgresConfig, get_postgres, init_postgres
from mvc_core.adapters.s3_AWS.s3_services import upload_file, generate_presigned_url
from mvc_core.adapters.IBKR.ibkr_services import fetch_and_upsert_trades

from dotenv import dotenv_values

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def get_trades(profile: str):
    """Get trades from a walk-forward backtest profile and save to CSV."""
    file_name = f"trades_{profile}.csv"
    file_path = f"/tmp/{file_name}"
    export_profile_trades_csv(profile, file_path)
    upload_file(file_path, file_name)
    url = generate_presigned_url(file_name)
    print(url)


def init_db():
    config = dotenv_values("/tmp/secrets/.env")
    pgconfig = PostgresConfig(
        host=config['POSTGRES_HOST'],
        port=int(config['POSTGRES_PORT']),
        database=config['POSTGRES_DATABASE'],
        username=config['POSTGRES_USERNAME'],
        password=config['POSTGRES_PASSWORD']
    )
    init_postgres(pgconfig)


def send_slack_notification(message: str):
    config = dotenv_values("/tmp/secrets/.env")
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


def main():
    try:
        init_db()

        get_trades("wf_sb11")
        fetch_and_upsert_trades("wf_sb11")

        get_trades("wf_rsi_sb11")
        fetch_and_upsert_trades("wf_rsi_sb11")

        get_trades("sb11_rsi_fut_shifted")
        fetch_and_upsert_trades("sb11_rsi_fut_shifted")

        get_trades("arabica_zscore_fut_shifted_wf")
        fetch_and_upsert_trades("arabica_zscore_fut_shifted_wf")

        get_trades("robusta_zscore_fut_shifted_wf")
        fetch_and_upsert_trades("robusta_zscore_fut_shifted_wf")

        send_slack_notification("✅ [trades] Updated data successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
        send_slack_notification(f"❌ [trades] Failed to update data: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

