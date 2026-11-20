#!/usr/bin/env python3
"""Kernel-replay worker: claims chunk files from an NFS queue and replays them with `checklist`
(Lean's own leanchecker replay routine `replayFromImports`, driven by an explicit module list).
Usage: check_worker.py <threads>
  queue: /u/mrubinst/alpoge_grh/check/todo/<chunk>  (one module name per line)
  claim = atomic rename into claimed/; result -> ok/<chunk> or bad/<chunk> (with leanchecker output).
A chunk that fails is re-run module by module so every failing module is named individually."""
import os, sys, subprocess, socket, time
Q = '/u/mrubinst/alpoge_grh/check'
W = '/tmp/mrubinst_alpoge'; T = W + '/leanprover--lean4---v4.33.1'; R = W + '/lean'
PK = ['batteries', 'Qq', 'aesop', 'proofwidgets', 'importGraph', 'LeanSearchClient', 'plausible', 'mathlib']
HOST = socket.gethostname().split('.')[0]
env = dict(os.environ, PATH=T + '/bin:/usr/bin:/bin', LEAN_NUM_THREADS=sys.argv[1],
           LEAN_PATH=':'.join(f'{R}/.lake/packages/{p}/.lake/build/lib/lean' for p in PK) + f':{R}/.lake/build/lib/lean:{T}/lib/lean')
for d in ('todo', 'claimed', 'ok', 'bad'): os.makedirs(f'{Q}/{d}', exist_ok=True)

CHK = '/u/mrubinst/alpoge_grh/tools/checklist/.lake/build/bin/checklist'
def run(listfile):
    p = subprocess.run([CHK, listfile], cwd=R, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode(errors='replace')

while True:
    if os.path.exists(f'{Q}/STOP'): break
    names = sorted(os.listdir(f'{Q}/todo'))
    if not names:
        time.sleep(20); continue
    got = None
    for n in names:
        try: os.rename(f'{Q}/todo/{n}', f'{Q}/claimed/{n}.{HOST}'); got = n; break
        except OSError: continue
    if not got: continue
    mods = open(f'{Q}/claimed/{got}.{HOST}').read().split()
    t0 = time.time(); rc, out = run(f'{Q}/claimed/{got}.{HOST}')
    ok_lines = [l for l in out.splitlines() if l.startswith('OK ')]
    good = rc == 0 and len(ok_lines) == len(mods) and f'SUMMARY checked={len(mods)} failed=0' in out
    open(f'{Q}/{"ok" if good else "bad"}/{got}', 'w').write(f'{HOST} {len(mods)} modules {time.time()-t0:.0f}s rc={rc}\n' + out)
    os.remove(f'{Q}/claimed/{got}.{HOST}')
