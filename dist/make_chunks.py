#!/usr/bin/env python3
"""Queue every staged (compiled) module not yet queued, in chunks of N, for check_worker.py."""
import os, sys
Q = '/u/mrubinst/alpoge_grh/check'; S = '/u/mrubinst/alpoge_grh/stage'; N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
os.makedirs(Q + '/todo', exist_ok=True)
qf = Q + '/queued.txt'
queued = set(open(qf).read().split()) if os.path.exists(qf) else set()
new = sorted(f[:-6] for f in os.listdir(S) if f.endswith('.olean') and f[:-6] not in queued)
k0 = len([l for l in open(Q + '/chunks.log')]) if os.path.exists(Q + '/chunks.log') else 0
with open(qf, 'a') as q, open(Q + '/chunks.log', 'a') as cl:
    for i in range(0, len(new), N):
        name = f'c{k0 + i//N:06d}'
        part = new[i:i+N]
        tmp = f'{Q}/{name}.tmp'; open(tmp, 'w').write('\n'.join(part) + '\n'); os.replace(tmp, f'{Q}/todo/{name}')
        q.write('\n'.join(part) + '\n'); cl.write(name + '\n')
print(f'queued {len(new)} new modules; total queued {len(queued) + len(new)}')
