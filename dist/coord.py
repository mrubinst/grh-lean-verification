#!/usr/bin/env python3
"""Distributed Lean build coordinator (runs on one host; agents on every host via ssh).
Correctness rule: a module is dispatched to host H only when every direct project import is
*present* on H, and a fetched module counts as present only once all of its own imports are
present there too — so every transitive import's .olean is on H's local disk before lean runs.
State that survives restarts: the NFS stage dir (a module is done iff stage/<M>.olean exists)."""
import os, sys, json, time, heapq, threading, queue, subprocess, collections

BASE = '/u/mrubinst/alpoge_grh'
SRC = '/tmp/mrubinst_alpoge/lean/src'
STAGE = BASE + '/stage'
HOSTS_FILE = BASE + '/dist/hosts.json'
STATUS = BASE + '/dist/STATUS'
EVLOG = BASE + '/dist/events.log'
AGENT = BASE + '/dist/agent.py'
ME = os.uname().nodename.split('.')[0]

# ---------- DAG ----------
mods, deps = {}, {}
for dp, _, fs in os.walk(SRC):
    for f in fs:
        if f.endswith('.lean'):
            p = os.path.join(dp, f); m = os.path.relpath(p, SRC)[:-5].replace('/', '.')
            imps, n = [], 0
            with open(p, encoding='utf-8', errors='replace') as fh:
                for ln in fh:
                    n += 1
                    if ln.startswith('import '): imps += ln.split()[1:]
            mods[m] = n; deps[m] = imps
for m in deps: deps[m] = sorted(set(d for d in deps[m] if d in mods and d != m))
rdeps = collections.defaultdict(list)
for m, ds in deps.items():
    for d in ds: rdeps[d].append(m)
# priority = longest weighted path from m to any sink (bottom level); weight ~ cost estimate
order, seen = [], set()
for r in mods:
    st = [(r, 0)]
    while st:
        n, k = st.pop()
        if k:
            order.append(n); continue
        if n in seen: continue
        seen.add(n); st.append((n, 1)); st += [(d, 0) for d in deps[n] if d not in seen]
blev = {}
for n in reversed(order):  # reverse topological: dependents first
    blev[n] = (mods[n] + 400) + max((blev[x] for x in rdeps[n]), default=0)
TOTAL = len(mods)

# ---------- state ----------
done = set(f[:-6] for f in os.listdir(STAGE) if f.endswith('.olean') and f[:-6] in mods) if os.path.isdir(STAGE) else set()
os.makedirs(STAGE, exist_ok=True)
failed, attempts = {}, collections.Counter()
running = {}                     # mod -> (host, t0)
present = collections.defaultdict(set); fetched = collections.defaultdict(set)
requested = collections.defaultdict(set)
remaining = {m: sum(1 for d in deps[m] if d not in done) for m in mods}
ready = [(-blev[m], m) for m in mods if m not in done and remaining[m] == 0]
heapq.heapify(ready)
evq = queue.Queue()
agents = {}                      # host -> dict(proc, slots, alive, lock)
durs = collections.deque(maxlen=2000); done_times = collections.deque(maxlen=5000)
t_start = time.time(); n_done_start = len(done)
evf = open(EVLOG, 'a')

def log(s):
    evf.write(time.strftime('%H:%M:%S ') + s + '\n'); evf.flush()

def send(h, d):
    a = agents.get(h)
    if not a or not a['alive']: return False
    try:
        with a['lock']:
            a['proc'].stdin.write(json.dumps(d) + '\n'); a['proc'].stdin.flush()
        return True
    except Exception:
        a['alive'] = False; return False

def reader(h, proc):
    for line in proc.stdout:
        try: evq.put((h, json.loads(line)))
        except Exception: pass
    evq.put((h, {"ev": "eof"}))

def launch(h):
    if h == ME: cmd = ['python3', '-I', AGENT]
    else: cmd = ['ssh', '-i', os.path.expanduser('~/.ssh/id_intra'), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=30', '-o', 'StrictHostKeyChecking=accept-new',
                 h, 'python3', '-I', AGENT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    old = agents.get(h, {})
    agents[h] = dict(proc=proc, slots=old.get('slots', 0), alive=True, lock=threading.Lock(), ready=False, t=time.time())
    threading.Thread(target=reader, args=(h, proc), daemon=True).start()
    log(f'launch agent {h}')

def promote(h, m):
    wl = [m]
    while wl:
        x = wl.pop()
        if x in present[h] or x not in fetched[h]: continue
        if all(d in present[h] for d in deps[x]):
            present[h].add(x); wl += [y for y in rdeps[x] if y in fetched[h]]

def broadcast_fetch(m, src_host):
    for h, a in agents.items():
        if a['alive'] and a['ready'] and h != src_host and m not in present[h] and m not in requested[h]:
            requested[h].add(m); send(h, {"op": "fetch", "mod": m})

def complete(m, h, t):
    done.add(m); running.pop(m, None); present[h].add(m); fetched[h].add(m)
    durs.append(t); done_times.append(time.time())
    for x in rdeps[m]:
        remaining[x] -= 1
        if remaining[x] == 0 and x not in done: heapq.heappush(ready, (-blev[x], x))
    broadcast_fetch(m, h)

def load_hosts():
    try: cfg = json.load(open(HOSTS_FILE))
    except Exception as e: log(f'hosts.json unreadable: {e}'); return
    for h, s in cfg.items():
        if h not in agents or (not agents[h]['alive'] and time.time() - agents[h]['t'] > 60):
            if s > 0: launch(h)
        if h in agents: agents[h]['slots'] = s
    for h in agents:
        if h not in cfg: agents[h]['slots'] = 0

def dispatch():
    free = {h: a['slots'] - sum(1 for v in running.values() if v[0] == h)
            for h, a in agents.items() if a['alive'] and a['ready']}
    if not any(v > 0 for v in free.values()): return
    deferred, scanned = [], 0
    while ready and scanned < 4000 and any(v > 0 for v in free.values()):
        pr, m = heapq.heappop(ready); scanned += 1
        if m in done or m in running: continue
        cands = [h for h, v in free.items() if v > 0 and all(d in present[h] for d in deps[m])]
        if not cands: deferred.append((pr, m)); continue
        h = max(cands, key=lambda x: free[x])
        if send(h, {"op": "compile", "mod": m}):
            running[m] = (h, time.time()); free[h] -= 1; attempts[m] += 1
        else: deferred.append((pr, m))
    for x in deferred: heapq.heappush(ready, x)

def write_status(final=False):
    now = time.time()
    recent = [t for t in done_times if now - t < 600]
    rate = len(recent) / 10.0 if recent else 0.0
    rem = TOTAL - len(done)
    per = collections.Counter(v[0] for v in running.values())
    lines = [f'time {time.strftime("%Y-%m-%d %H:%M:%S %Z")}',
             f'done {len(done)} / {TOTAL}  ({100.0*len(done)/TOTAL:.2f}%)  failed {len(failed)}  running {len(running)}  ready {len(ready)}',
             f'rate_last10min {rate:.1f} modules/min  eta_min {rem/rate:.0f}' if rate else 'rate n/a',
             f'mean_compile_s(last2000) {sum(durs)/len(durs):.1f}' if durs else '',
             'hosts: ' + '  '.join(f'{h}:{per[h]}/{a["slots"]}{"" if a["alive"] else "(down)"} have={len(present[h])}' for h, a in sorted(agents.items())),
             'failed: ' + ' '.join(sorted(failed))[:2000]]
    if final: lines.append('ALL_DONE' if len(done) == TOTAL else f'STOPPED_INCOMPLETE done={len(done)} failed={len(failed)}')
    tmp = STATUS + '.tmp'; open(tmp, 'w').write('\n'.join(lines) + '\n'); os.replace(tmp, STATUS)

log(f'start: {TOTAL} modules, {len(done)} already staged, {len(ready)} ready')
load_hosts()
last_hosts = last_status = time.time()
def events():
    try: yield evq.get(timeout=2)
    except queue.Empty: return
    for _ in range(20000):
        try: yield evq.get_nowait()
        except queue.Empty: return

while True:
  for h, e in events():
    if True:
          ev = e['ev']
          if ev == 'inv':
              for m in e['mods']:
                  if m in done: fetched[h].add(m)
              for m in list(fetched[h]): promote(h, m)
              agents[h]['ready'] = True
              miss = [m for m in done if m not in present[h]]
              for m in sorted(miss, key=lambda x: -blev[x]):
                  requested[h].add(m); send(h, {"op": "fetch", "mod": m})
              log(f'{h} ready: inventory {len(e["mods"])}, present {len(present[h])}, fetching {len(miss)}')
          elif ev == 'have':
              fetched[h].add(e['mod']); promote(h, e['mod'])
          elif ev == 'done':
              complete(e['mod'], h, e['t'])
          elif ev == 'fail':
              m = e['mod']; running.pop(m, None)
              log(f'FAIL {m} on {h} rc={e.get("rc")} t={e.get("t"):.0f} {e.get("err","")}')
              if attempts[m] < 2: heapq.heappush(ready, (-blev[m], m))
              else: failed[m] = h
          elif ev == 'fetchfail':
              requested[h].discard(e['mod']); log(f'fetchfail {e["mod"]} on {h}: {e.get("err")}')
          elif ev == 'eof':
              agents[h]['alive'] = False; agents[h]['ready'] = False; agents[h]['t'] = time.time()
              for m, (hh, _) in list(running.items()):
                  if hh == h: running.pop(m); heapq.heappush(ready, (-blev[m], m))
              present[h].clear(); fetched[h].clear(); requested[h].clear()
              log(f'agent {h} EOF; requeued its running modules')
  dispatch()
  now = time.time()
  if now - last_hosts > 60: load_hosts(); last_hosts = now
  if now - last_status > 15: write_status(); last_status = now
  if len(done) + len(failed) >= TOTAL or (not running and not ready and failed and evq.empty()):
      if not running:
          write_status(final=True); log('finished'); break
