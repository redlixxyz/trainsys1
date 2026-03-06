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

# Door position labels (index → abbreviation)
# 0 = FR (Front Right)  1 = FL (Front Left)
# 2 = BR (Back Right)   3 = BL (Back Left)
DOOR_LABELS = ['FR', 'FL', 'BR', 'BL']

# PSI scale and alert thresholds
PSI_MAX             = 200
BRAKE_THRESHOLD     = 150   # EC:45 alert when brake_psi exceeds this
HYDRAULIC_MIN       = 50    # EC:45 alert when hydraulic_psi falls below this
HYDRAULIC_THRESHOLD = 100   # mid-range marker line shown on gauge


def log_login(train_number, endstation, driver, wagons):
    ts = datetime.utcnow().isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f"{ts},{train_number},{endstation},{driver},{wagons}\n")


def make_train(wagons, train_number, endstation, driver):
    wagons_list = []
    for i in range(wagons):
        wagons_list.append({
            'id': i + 1,
            # four doors per wagon: FR=0, FL=1, BR=2, BL=3
            'doors': ['closed'] * 4,
        })
    return {
        'train_number': train_number,
        'endstation':   endstation,
        'driver':       driver,
        'wagons':       wagons_list,
        'brake_psi':    random.randint(80, 170),
        'hydraulic_psi': random.randint(60, 140),
        'created':      datetime.utcnow().isoformat(),
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        wagons = max(1, min(8, int(request.form.get('wagons', 4))))
        return redirect(url_for('login', wagons=wagons))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        wagons = max(1, min(8, int(request.form.get('wagons'))))
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
    wagons = max(1, min(8, int(request.args.get('wagons', 4))))
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


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(os.path.join(os.getcwd(), 'audio'), filename)


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

    errors = []

    # Door fault errors (EC:35)
    for w in TRAIN['wagons']:
        for di, state in enumerate(w['doors']):
            if state == 'error':
                pos = DOOR_LABELS[di]
                errors.append({
                    'code':     35,
                    'text':     f"DOOR {w['id']}{pos} FAILURE",
                    'wagon':    w['id'],
                    'door':     di,
                    'priority': 1,
                })

    # PSI errors (EC:45)
    brake_psi = TRAIN.get('brake_psi', 0)
    hydr_psi  = TRAIN.get('hydraulic_psi', 0)
    if brake_psi > BRAKE_THRESHOLD:
        errors.append({'code': 45, 'text': 'BRAKE PSI HIGH',    'priority': 2})
    if hydr_psi < HYDRAULIC_MIN:
        errors.append({'code': 45, 'text': 'HYDRAULIC PSI LOW', 'priority': 2})

    # Sort: priority asc, then code asc
    errors.sort(key=lambda e: (e['priority'], e['code']))

    return jsonify({
        'ok':    True,
        'train': TRAIN,
        'time':  datetime.now().isoformat(),
        'errors': errors,
        'psi_max':                PSI_MAX,
        'brake_threshold_pct':    BRAKE_THRESHOLD    / PSI_MAX,
        'hydraulic_threshold_pct': HYDRAULIC_THRESHOLD / PSI_MAX,
    })


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


@app.route('/api/set-psi', methods=['POST'])
def api_set_psi():
    """Set global brake or hydraulic PSI.
    POST JSON: { "kind": "brake" | "hydraulic", "value": 0-200 }
    """
    global TRAIN
    if TRAIN is None:
        return jsonify({'ok': False})
    data  = request.get_json() or {}
    kind  = data.get('kind')
    value = max(0, min(PSI_MAX, int(data.get('value', 100))))
    if kind == 'brake':
        TRAIN['brake_psi'] = value
    elif kind == 'hydraulic':
        TRAIN['hydraulic_psi'] = value
    else:
        return jsonify({'ok': False, 'msg': 'kind must be brake or hydraulic'})
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
