// Door position labels (index → abbreviation)
// 0 = FR (Front Right), 1 = FL (Front Left), 2 = BR (Back Right), 3 = BL (Back Left)
const DOOR_LABELS  = ['FR', 'FL', 'BR', 'BL'];

// Top strip  → right-side doors: FR (0) and BR (2)
// Bottom strip → left-side doors: FL (1) and BL (3)
const TOP_DOORS    = [0, 2];
const BOTTOM_DOORS = [1, 3];

/* ─── Fetch ──────────────────────────────────────────────── */
async function fetchStatus() {
  const r = await fetch('/api/status');
  return r.json();
}

/* ─── Clock: 24-h format, DD.MM.YYYY ────────────────────── */
function tickClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const mo = String(now.getMonth() + 1).padStart(2, '0');
  const yy = now.getFullYear();
  const tEl = document.getElementById('h-time');
  const dEl = document.getElementById('h-date');
  if (tEl) tEl.textContent = `${hh}:${mm}`;
  if (dEl) dEl.textContent = `${dd}.${mo}.${yy}`;
}

/* ─── Header metadata ────────────────────────────────────── */
function renderHeader(train) {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v || '—';
  };
  set('h-train-number', train.train_number);
  set('h-endstation',   train.endstation);
  set('h-driver',       train.driver);
}

/* ─── Error / message area ───────────────────────────────── */
function renderErrors(errors) {
  const primary   = document.getElementById('primary-error');
  const secondary = document.getElementById('secondary-errors');
  const noErr     = document.getElementById('no-errors');

  secondary.innerHTML = '';

  if (!errors || errors.length === 0) {
    primary.classList.add('hidden');
    noErr.classList.remove('hidden');
    return;
  }

  noErr.classList.add('hidden');

  // Highest-priority error → primary line (red, large, underlined)
  primary.classList.remove('hidden');
  primary.textContent = `EC:${errors[0].code}  ${errors[0].text}`;

  // Remaining errors → secondary lines (black, normal weight)
  errors.slice(1).forEach(err => {
    const row = document.createElement('div');
    row.className = 'secondary-error';
    row.textContent = `EC:${err.code}  ${err.text}`;
    secondary.appendChild(row);
  });
}

/* ─── PSI vertical gauges ────────────────────────────────── */
function renderPSI(train, psiMax, brakeThreshPct, hydThreshPct) {
  const brakePsi = train.brake_psi    || 0;
  const hydPsi   = train.hydraulic_psi || 0;
  const max      = psiMax || 200;

  function updateBar(barId, valId, threshId, psi, threshPct) {
    const fillPct = Math.min(100, (psi / max) * 100).toFixed(1);
    const bar   = document.getElementById(barId);
    const val   = document.getElementById(valId);
    const thres = document.getElementById(threshId);
    if (bar)   bar.style.height   = fillPct + '%';
    if (val)   val.textContent    = psi + ' PSI';
    if (thres) thres.style.bottom = (threshPct * 100).toFixed(1) + '%';
  }

  updateBar('brake-bar',     'brake-val',     'brake-threshold',     brakePsi, brakeThreshPct);
  updateBar('hydraulic-bar', 'hydraulic-val', 'hydraulic-threshold', hydPsi,   hydThreshPct);
}

/* ─── Bottom train overview ──────────────────────────────── */
function renderTrainOverview(wagons) {
  const container = document.getElementById('wagons-overview');
  container.innerHTML = '';

  wagons.forEach(w => {
    const unit = document.createElement('div');
    unit.className = 'wagon-unit';

    // Build a horizontal door-segment strip
    function makeStrip(doorIndices, cls) {
      const strip = document.createElement('div');
      strip.className = `door-strip ${cls}`;
      doorIndices.forEach(di => {
        const seg   = document.createElement('div');
        const state = (w.doors[di] || 'closed');
        seg.className = `door-seg ${state}`;
        seg.title = `Wagon ${w.id} \u2013 ${DOOR_LABELS[di]} \u2013 ${state}`;
        seg.addEventListener('click', () => toggleDoor(w.id, di));
        strip.appendChild(seg);
      });
      return strip;
    }

    // Wagon body (shows wagon number)
    const body = document.createElement('div');
    body.className = 'wagon-body';
    const num = document.createElement('span');
    num.className = 'wagon-num';
    num.textContent = w.id;
    body.appendChild(num);

    unit.appendChild(makeStrip(TOP_DOORS,    'top-strip'));   // right-side doors
    unit.appendChild(body);
    unit.appendChild(makeStrip(BOTTOM_DOORS, 'bot-strip'));   // left-side doors
    container.appendChild(unit);
  });
}

/* ─── Door toggle (click on a segment cycles its state) ─── */
async function toggleDoor(wagonId, doorIdx) {
  try {
    await fetch('/api/set-door', {
      method:  'POST',
      headers: { 'content-type': 'application/json' },
      body:    JSON.stringify({ wagon: wagonId, door: doorIdx }),
    });
    await poll();
  } catch (e) {
    console.error('toggleDoor error:', e);
  }
}

/* ─── Main poll loop ─────────────────────────────────────── */
async function poll() {
  try {
    const res = await fetchStatus();
    if (res.ok) {
      renderHeader(res.train);
      renderErrors(res.errors);
      renderPSI(
        res.train,
        res.psi_max,
        res.brake_threshold_pct,
        res.hydraulic_threshold_pct
      );
      renderTrainOverview(res.train.wagons);
    }
  } catch (e) {
    console.error('poll error:', e);
  }
}

window.poll = poll;

tickClock();
setInterval(tickClock, 1000);
setInterval(poll, 2000);
poll();
