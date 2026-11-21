#!/usr/bin/env python3
"""Final sweep for the kernel replay: every module of the project must have an 'OK <module>' line in
check/ok/*. Modules without one (e.g. chunks interrupted by the operating system) are queued again.
Prints the counts; 'COMPLETE' only when all modules are OK and nothing is pending."""
import os, sys
B = '/u/mrubinst/alpoge_grh'; Q = B + '/check'
allm = set(f[:-6] for f in os.listdir(B + '/stage') if f.endswith('.olean'))
ok = set()
for f in os.listdir(Q + '/ok'):
    for l in open(f'{Q}/ok/{f}'):
        if l.startswith('OK '): ok.add(l.split()[1])
fails = [l.strip() for d in ('ok', 'bad') for f in os.listdir(f'{Q}/{d}') for l in open(f'{Q}/{d}/{f}') if l.startswith('FAIL ')]
pending = set()
for d in ('todo', 'claimed'):
    for f in os.listdir(f'{Q}/{d}'): pending |= set(open(f'{Q}/{d}/{f}').read().split())
missing = sorted(allm - ok - pending)
print(f'modules={len(allm)} ok={len(ok & allm)} pending={len(pending - ok)} missing={len(missing)} FAIL_lines={len(fails)} extra_ok={len(ok - allm)}')
for l in fails[:20]: print(l[:300])
if '--requeue' in sys.argv and missing:
    N = 100
    for i in range(0, len(missing), N):
        name = f's{os.getpid()}_{i//N:05d}'
        open(f'{Q}/{name}.tmp', 'w').write('\n'.join(missing[i:i+N]) + '\n'); os.replace(f'{Q}/{name}.tmp', f'{Q}/todo/{name}')
    print(f'requeued {len(missing)} modules')
if len(ok & allm) == len(allm) == 175187 and not fails: print('COMPLETE: all 175187 modules replayed OK')
