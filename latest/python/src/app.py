from flask import Flask, Response, request
from dotenv import dotenv_values
from datetime import date
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import hmac
import json
import subprocess
import threading
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)

logger = logging.getLogger(__name__)

config = dotenv_values("/tmp/secrets/.env")

# Hard cap so a hung child (slow TLS handshake, socket in CLOSE_WAIT)
# cannot block the Flask thread forever.
SUBPROCESS_TIMEOUT = int(config.get('SUBPROCESS_TIMEOUT', '300'))


def send_slack_notification(message):
    env_tag = (config.get('S3_PREFIX') or '').strip('/')
    prefix = f"[{env_tag}] " if env_tag else ""
    try:
        WebClient(token=config['SLACK_TOKEN']).chat_postMessage(
            channel=config['SLACK_CHANNEL'],
            text=f"{prefix}{message}",
            username=config['SLACK_USERNAME']
        )
    except SlackApiError as exc:
        logger.error("Slack notification failed: %s", exc)


def run_script(script, *args):
    try:
        result = subprocess.run(
            ['python3', f'/app/src/{script}', *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "Timeout after %ss running %s", SUBPROCESS_TIMEOUT, script
        )
        return subprocess.CompletedProcess(
            args=exc.cmd,
            returncode=1,
            stdout=exc.stdout or '',
            stderr=exc.stderr or ''
        )
    logger.debug(result.stdout)
    logger.debug(result.stderr)
    return result


@app.before_request
def require_token():
    # Every endpoint starts a job, so refuse anything without the right token.
    # 401 (rather than 200 "{}") makes a token mismatch fail loudly in
    # the-deepcore-app's workers instead of looking like a successful run.
    token = request.args.get('token') or ''
    if not hmac.compare_digest(token, config['IBGATEWAY_TOKEN']):
        logger.warning("Invalid token for %s from %s", request.path, request.remote_addr)
        return Response(
            response='{"error": "invalid token"}',
            status=401,
            mimetype='application/json'
        )

@app.route('/')

@app.route('/handle_request', methods=['GET'])

def handle_request():
    result = run_script('test_jobs.py')
    if result.returncode != 0:
        return Response(
            response=json.dumps({'error': f'{request.path} failed'}),
            status=500,
            mimetype='application/json'
        )

    return Response(
        response='{}',
        status=200,
        headers=[]
    )

@app.route('/handle_request_client', methods=['GET'])

def handle_request_client():
    result = run_script('test_plot_clients.py')
    if result.returncode != 0:
        return Response(
            response=json.dumps({'error': f'{request.path} failed'}),
            status=500,
            mimetype='application/json'
        )

    return Response(
        response='{}',
        status=200,
        headers=[]
    )

@app.route('/handle_trades', methods=['GET'])

def handle_trades():
    result = run_script('test_trades.py')
    if result.returncode != 0:
        return Response(
            response=json.dumps({'error': f'{request.path} failed'}),
            status=500,
            mimetype='application/json'
        )

    return Response(
        response='{}',
        status=200,
        headers=[]
    )

# test_compass.py exit codes (see EXIT_* there).
COMPASS_NOTHING_NEW = 10
# the-deepcore-app calls /handle_compass once a day, right after
# /handle_trades. When that first attempt fails, or finds no new trade to
# post (the trades may not be written yet), it is run once more 10 minutes
# later, in the background so the caller's request doesn't wait for it.
COMPASS_RETRY_DELAY = int(config.get('COMPASS_RETRY_DELAY', '600'))


class CompassRetry:
    """Serialises at most one pending-or-running retry.

    The slot stays occupied for the full lifetime of the pending AND
    running retry so a concurrent /handle_compass cannot queue a second
    retry on top of one already executing.
    """

    def __init__(self, delay):
        self.delay = delay
        self.lock = threading.Lock()
        self.timer = None
        self.running = False

    def schedule(self, callback):
        """Return True iff a new retry was armed."""
        with self.lock:
            if self.timer is not None or self.running:
                logger.info("Compass retry already scheduled or running")
                return False
            timer = threading.Timer(self.delay, self._run, args=(callback,))
            timer.daemon = True
            try:
                timer.start()
            except RuntimeError as exc:
                # Thread exhaustion / kernel pressure: leave the slot free
                # so the next call can try again instead of being wedged.
                logger.error("Compass retry Timer.start() failed: %s", exc)
                return False
            self.timer = timer
        logger.info("Compass retry scheduled in %ss", self.delay)
        return True

    def _run(self, callback):
        with self.lock:
            self.timer = None
            self.running = True
        try:
            callback()
        finally:
            with self.lock:
                self.running = False


def retry_compass_callback():
    result = run_script('test_compass.py', '--retry')
    logger.info("Compass retry finished with exit code %s", result.returncode)


compass_retry = CompassRetry(COMPASS_RETRY_DELAY)


@app.route('/handle_compass', methods=['GET'])

def handle_compass():
    result = run_script('test_compass.py')

    if result.returncode == 0:
        return Response(response='{}', status=200, headers=[])

    if result.returncode == COMPASS_NOTHING_NEW:
        reason = "no new trade yet"
        http_status = 200
    else:
        reason = "previous attempt failed"
        http_status = 500

    if compass_retry.schedule(retry_compass_callback):
        send_slack_notification(
            f"ℹ️ [compass] Retrying in {COMPASS_RETRY_DELAY // 60} min ({reason})"
        )

    if http_status == 200:
        return Response(response='{}', status=200, headers=[])

    return Response(
        response=json.dumps({'error': f'{request.path} failed'}),
        status=500,
        mimetype='application/json'
    )

@app.route('/cepea_differential', methods=['GET'])

def handle_cepea_differential():
    try:
        cepea_date = date.fromisoformat(request.args.get('date', ''))
        arabica = float(request.args['arabica'])
        robusta = float(request.args['robusta'])
    except (KeyError, ValueError):
        return Response(
            response='{"error": "expected date=YYYY-MM-DD, arabica=<float>, robusta=<float>"}',
            status=400,
            mimetype='application/json'
        )

    result = run_script(
        'cepea_differential.py',
        '--date', cepea_date.isoformat(),
        '--arabica', str(arabica),
        '--robusta', str(robusta)
    )
    if result.returncode != 0:
        return Response(
            response=json.dumps({'error': f'{request.path} failed'}),
            status=500,
            mimetype='application/json'
        )

    # Last stdout line is the JSON result; ib_insync may log before it
    return Response(
        response=result.stdout.strip().splitlines()[-1],
        status=200,
        mimetype='application/json'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5000', debug=True)
