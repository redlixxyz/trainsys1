// Poll server for status and render train, doors and gauges
async function fetchStatus(){
  const r = await fetch('/api/status');
  return r.json();
}

function mkDoorEl(wagonIdx, doorIdx, state){
  const d = document.createElement('div');
  d.className = 'door ' + (state === 'open' ? 'open' : state === 'error' ? 'error' : '');
  d.textContent = state === 'open' ? 'OPEN' : state === 'error' ? 'ERR' : 'CLOSED';
  d.onclick = async ()=>{
     // cycle state on click
     try{
      await fetch('/api/set-door', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({wagon:wagonIdx+1,door:doorIdx})});
      // refresh immediately after change
      await poll();
     }catch(e){console.error(e)}
  };
  return d;
}

function renderTrain(train){
  const row = document.getElementById('train-row');
  row.innerHTML = '';
  train.wagons.forEach((w, wi)=>{
    const wdiv = document.createElement('div');
    wdiv.className = 'wagon';
    // subtle perspective transform for drone view
    wdiv.style.transform = 'perspective(800px) translateY(' + (wi%2?6:0) + 'px)';
    const doors = document.createElement('div');
    doors.className = 'doors';
    w.doors.forEach((s, di)=>{
      doors.appendChild(mkDoorEl(wi, di, s));
    });
    wdiv.appendChild(doors);
    const foot = document.createElement('div');
    foot.style.position='absolute';foot.style.bottom='8px';foot.style.left='12px';foot.style.fontSize='13px';foot.style.color='#555';
    foot.textContent = 'W ' + w.id;
    wdiv.appendChild(foot);
    row.appendChild(wdiv);
  });
}

function renderGauges(train){
  const gnode = document.getElementById('gauges');
  gnode.innerHTML = '';
  train.wagons.forEach(w=>{
    const box = document.createElement('div');
    box.className = 'gauge';
    const title = document.createElement('div'); title.textContent = 'W ' + w.id;
    title.style.fontWeight='700';
    const bar = document.createElement('div'); bar.className = 'bar';
    const i = document.createElement('i'); i.style.width = (w.pressure||0) + '%';
    bar.appendChild(i);
    const pct = document.createElement('div'); pct.style.fontSize='13px';pct.style.color='#333';pct.textContent = (w.pressure||0) + '%';
    box.appendChild(title);box.appendChild(bar);box.appendChild(pct);
    gnode.appendChild(box);
  });
}

function renderStatus(errors){
  const box = document.getElementById('status-box');
  if(!errors || errors.length===0){
    box.textContent = 'All systems are up.';
    box.style.color = '#0a0';
    return;
  }
  box.innerHTML = '';
  const h = document.createElement('div'); h.textContent = 'Errors'; h.style.fontWeight='600';
  box.appendChild(h);
  errors.forEach(e=>{
    const li = document.createElement('div'); li.textContent = `W${e.wagon} door ${e.door}`;
    li.style.color='#c33';box.appendChild(li);
  });
}

function tickClock(){
  const el = document.getElementById('top-time');
  const now = new Date();
  el.textContent = now.toLocaleString();
}

async function poll(){
  try{
    const res = await fetchStatus();
    if(res.ok){
        const train = res.train;
        // header metadata
        try{
          const tn = document.getElementById('train-number'); if(tn) tn.textContent = train.train_number || '—';
          const te = document.getElementById('train-end'); if(te) te.textContent = train.endstation || '—';
          const td = document.getElementById('train-driver'); if(td) td.textContent = train.driver || '—';
        }catch(e){}
        renderTrain(train);
        renderGauges(train);
        renderStatus(res.errors);
    }
  }catch(e){console.error(e)}
}

  // expose poll for internal use
  window.poll = poll;

tickClock();
setInterval(tickClock,1000);
setInterval(poll,1000);
poll();
