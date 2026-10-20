from flask import Flask, Response, request
from dotenv import dotenv_values
from datetime import date
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


def run_script(script, *args):
    result = subprocess.run(
        ['python3', f'/app/src/{script}', *args],
        capture_output=True,
        text=True
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
COMPASS_NOTHING_NEW = 2
# the-deepcore-app calls /handle_compass once a day, right after
# /handle_trades. When that first attempt fails, or finds no new trade to
# post (the trades may not be written yet), it is run once more 10 minutes
# later, in the background so the caller's request doesn't wait for it.
COMPASS_RETRY_DELAY = 600
compass_retry_lock = threading.Lock()
compass_retry_timer = None


def retry_compass():
    global compass_retry_timer
    with compass_retry_lock:
        compass_retry_timer = None
    result = run_script('test_compass.py', '--retry')
    logger.info("Compass retry finished with exit code %s", result.returncode)


def schedule_compass_retry():
    global compass_retry_timer
    with compass_retry_lock:
        if compass_retry_timer is not None:
            logger.info("Compass retry already scheduled")
            return
        compass_retry_timer = threading.Timer(COMPASS_RETRY_DELAY, retry_compass)
        compass_retry_timer.daemon = True
        compass_retry_timer.start()
    logger.info("Compass retry scheduled in %ss", COMPASS_RETRY_DELAY)


@app.route('/handle_compass', methods=['GET'])

def handle_compass():
    result = run_script('test_compass.py')
    if result.returncode != 0:
        schedule_compass_retry()
    if result.returncode not in (0, COMPASS_NOTHING_NEW):
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
