from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import csv
import os
from datetime import datetime
import random

app = Flask(__name__)

# Simple in-memory train store
TRAIN = None
LOG_FILE = os.path.join('logs', 'logins.csv')
os.makedirs('logs', exist_ok=True)
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write('timestamp,train_number,endstation,driver,wagons\n')


def log_login(train_number, endstation, driver, wagons):
    ts = datetime.utcnow().isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f"{ts},{train_number},{endstation},{driver},{wagons}\n")


def make_train(wagons, train_number, endstation, driver):
    wagons_list = []
    for i in range(wagons):
        wagons_list.append({
            'id': i + 1,
            # four doors: 0..3
            'doors': ['closed'] * 4,
            # pressure 0-100
            'pressure': random.randint(70, 100)
        })
    return {
        'train_number': train_number,
        'endstation': endstation,
        'driver': driver,
        'wagons': wagons_list,
        'created': datetime.utcnow().isoformat()
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        wagons = int(request.form.get('wagons', 3))
        return redirect(url_for('login', wagons=wagons))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        wagons = int(request.form.get('wagons'))
        train_number = request.form.get('train_number')
        endstation = request.form.get('endstation')
        driver = request.form.get('driver')
        global TRAIN
        TRAIN = make_train(wagons, train_number, endstation, driver)
        # log login event
        try:
            log_login(train_number, endstation, driver, wagons)
        except Exception:
            pass
        return redirect(url_for('main'))
    # show empty form (user must fill in values)
    wagons = int(request.args.get('wagons', 3))
    return render_template('login.html', wagons=wagons)


@app.route('/logout')
def logout():
    global TRAIN
    TRAIN = None
    return redirect(url_for('index'))


@app.route('/logs/<path:filename>')
def serve_logs(filename):
    # serve simple CSV login log for auditing
    return send_from_directory(os.path.join(os.getcwd(), 'logs'), filename)


@app.route('/admin')
def admin():
    # parse the log file and render a simple admin table (most recent first)
    logpath = LOG_FILE
    entries = []
    try:
        with open(logpath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append({
                    'timestamp': row.get('timestamp',''),
                    'train_number': row.get('train_number',''),
                    'endstation': row.get('endstation',''),
                    'driver': row.get('driver',''),
                    'wagons': row.get('wagons','')
                })
    except Exception:
        entries = []
    entries = list(reversed(entries))
    return render_template('admin.html', logins=entries)


@app.route('/main')
def main():
    if TRAIN is None:
        return redirect(url_for('index'))
    return render_template('main.html')


@app.route('/api/status')
def api_status():
    if TRAIN is None:
        return jsonify({'ok': False, 'msg': 'no train configured'})
    # compute errors
    errors = []
    for w in TRAIN['wagons']:
        for di, d in enumerate(w['doors']):
            if d == 'error':
                errors.append({'wagon': w['id'], 'door': di})
    return jsonify({'ok': True, 'train': TRAIN, 'time': datetime.now().isoformat(), 'errors': errors})


@app.route('/api/set-door', methods=['POST'])
def api_set_door():
    global TRAIN
    if TRAIN is None:
        return jsonify({'ok': False})
    data = request.get_json() or {}
    w = int(data.get('wagon', 1)) - 1
    d = int(data.get('door', 0))
    state = data.get('state')
    if w < 0 or w >= len(TRAIN['wagons']):
        return jsonify({'ok': False})
    # cycle or set
    if state:
        TRAIN['wagons'][w]['doors'][d] = state
    else:
        cur = TRAIN['wagons'][w]['doors'][d]
        nxt = 'open' if cur == 'closed' else 'error' if cur == 'open' else 'closed'
        TRAIN['wagons'][w]['doors'][d] = nxt
    return jsonify({'ok': True, 'doors': TRAIN['wagons'][w]['doors']})


@app.route('/api/set-pressure', methods=['POST'])
def api_set_pressure():
    global TRAIN
    if TRAIN is None:
        return jsonify({'ok': False})
    data = request.get_json() or {}
    w = int(data.get('wagon', 1)) - 1
    val = int(data.get('pressure', 80))
    if w < 0 or w >= len(TRAIN['wagons']):
        return jsonify({'ok': False})
    TRAIN['wagons'][w]['pressure'] = max(0, min(100, val))
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
