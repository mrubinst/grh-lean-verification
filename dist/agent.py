#!/usr/bin/env python3
"""Per-host build agent. Reads JSON commands on stdin, writes JSON events on stdout.
  {"op":"compile","mod":M}  -> compile M locally, publish .olean to NFS stage, emit {"ev":"done"|"fail",...}
  {"op":"fetch","mod":M}    -> copy M.olean from NFS stage into the local tree, emit {"ev":"have",...}
On start it emits {"ev":"inv","mods":[...]} listing every project .olean already present locally."""
import sys, os, json, subprocess, threading, queue, time, shutil, resource, socket

W = '/tmp/mrubinst_alpoge'
T = W + '/leanprover--lean4---v4.33.1'
LEAN = T + '/bin/lean'
ROOT = W + '/lean'
SRC = ROOT + '/src'
OUT = ROOT + '/.lake/build/lib/lean'
SETUPD = W + '/setup'
TMPD = W + '/tmpout'
STAGE = '/u/mrubinst/alpoge_grh/stage'
FAILD = '/u/mrubinst/alpoge_grh/fail'
PKGS = ['Cli', 'batteries', 'Qq', 'aesop', 'proofwidgets', 'importGraph', 'LeanSearchClient', 'plausible', 'mathlib']
LP = ':'.join([p for p in (f'{ROOT}/.lake/packages/{k}/.lake/build/lib/lean' for k in PKGS) if os.path.isdir(p)]
              + [OUT, T + '/lib/lean'])
BASE_OPTS = {"relaxedAutoImplicit": False, "pp.unicode.fun": True, "maxSynthPendingDepth": 3,
             "maxHeartbeats": 4000000, "autoImplicit": False}
HOST = socket.gethostname().split('.')[0]
lock = threading.Lock()

def emit(d):
    with lock:
        sys.stdout.write(json.dumps(d) + '\n'); sys.stdout.flush()

def rel(m): return m.replace('.', '/')

def opts_for(m):
    o = dict(BASE_OPTS)
    if m.startswith('GroundTheory.LocalFields.') or m.startswith('GroundTheory.GlobalFields.'):
        o["synthInstance.maxHeartbeats"] = 400000      # lean_lib GroundTheoryFields in lakefile.toml
    return o

def put(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + f'.tmp.{HOST}.{threading.get_ident()}'
    shutil.copyfile(src, tmp); os.replace(tmp, dst)

def compile_(m):
    t0 = time.time()
    try:
        r = rel(m)
        setup = f'{SETUPD}/{m}.json'
        with open(setup, 'w') as f:
            json.dump({"plugins": [], "package": "tree", "options": opts_for(m), "name": m,
                       "isModule": False, "importArts": {}, "dynlibs": []}, f)
        to, ti = f'{TMPD}/{m}.olean', f'{TMPD}/{m}.ilean'
        env = dict(os.environ, LEAN_PATH=LP)
        p = subprocess.run([LEAN, '--tstack=400000', f'{SRC}/{r}.lean', '-o', to, '-i', ti, '--setup', setup],
                           cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        dt = time.time() - t0
        if p.returncode != 0 or not os.path.exists(to):
            os.makedirs(FAILD, exist_ok=True)
            with open(f'{FAILD}/{m}.{HOST}.log', 'wb') as f: f.write(p.stdout)
            emit({"ev": "fail", "mod": m, "rc": p.returncode, "t": dt}); return
        dst = f'{OUT}/{r}.olean'
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(ti, f'{OUT}/{r}.ilean'); os.replace(to, dst)
        put(dst, f'{STAGE}/{m}.olean')
        os.remove(setup)
        emit({"ev": "done", "mod": m, "t": round(dt, 2)})
    except Exception as e:
        emit({"ev": "fail", "mod": m, "rc": -1, "err": repr(e), "t": time.time() - t0})

fq = queue.Queue()
def fetcher():
    while True:
        m = fq.get()
        try:
            put(f'{STAGE}/{m}.olean', f'{OUT}/{rel(m)}.olean'); emit({"ev": "have", "mod": m})
        except Exception as e:
            emit({"ev": "fetchfail", "mod": m, "err": repr(e)})

def main():
    resource.setrlimit(resource.RLIMIT_NOFILE, (1048576, 1048576))
    for d in (SETUPD, TMPD, OUT): os.makedirs(d, exist_ok=True)
    inv = []
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if f.endswith('.olean'):
                inv.append(os.path.relpath(os.path.join(dp, f), OUT)[:-6].replace('/', '.'))
    emit({"ev": "inv", "host": HOST, "mods": inv})
    for _ in range(16): threading.Thread(target=fetcher, daemon=True).start()
    for line in sys.stdin:
        c = json.loads(line)
        if c['op'] == 'compile': threading.Thread(target=compile_, args=(c['mod'],), daemon=True).start()
        elif c['op'] == 'fetch': fq.put(c['mod'])
    emit({"ev": "bye"})

if __name__ == '__main__':
    main()
