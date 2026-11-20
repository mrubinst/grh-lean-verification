import os, sys, re, collections
src = sys.argv[1]
mods = {}
for root, _, files in os.walk(src):
    for f in files:
        if f.endswith('.lean'):
            p = os.path.join(root, f)
            m = os.path.relpath(p, src)[:-5].replace('/', '.')
            imps, lines = [], 0
            with open(p, encoding='utf-8', errors='replace') as fh:
                for ln in fh:
                    lines += 1
                    s = ln.strip()
                    if s.startswith('import '):
                        imps += s.split()[1:]
            mods[m] = (imps, lines)
deps = {m: [i for i in v[0] if i in mods] for m, v in mods.items()}
sys.setrecursionlimit(1000000)
# critical path by lines (proxy for time) and depth
order = []; state = {}
for m in mods:
    stack = [(m, 0)]
    while stack:
        n, k = stack.pop()
        if k == 0:
            if state.get(n): continue
            state[n] = 1; stack.append((n, 1))
            for d in deps[n]:
                if not state.get(d): stack.append((d, 0))
        else:
            if state[n] == 1: state[n] = 2; order.append(n)
cp, depth = {}, {}
for n in order:
    cp[n] = mods[n][1] + max((cp[d] for d in deps[n]), default=0)
    depth[n] = 1 + max((depth[d] for d in deps[n]), default=0)
tot = sum(v[1] for v in mods.values())
print("modules", len(mods), "lines", tot)
print("critical path lines (Main)", cp['Main'], "depth", depth['Main'])
print("max cp", max(cp.values()), "max depth", max(depth.values()))
print("parallelism ratio total/cp = %.0f" % (tot / max(cp.values())))
reach = set(); st = ['Main', 'Statements']
while st:
    n = st.pop()
    if n in reach: continue
    reach.add(n); st += deps[n]
print("modules reachable from Main", len(reach), "lines", sum(mods[n][1] for n in reach))
# width profile by depth
h = collections.Counter(depth[n] for n in reach)
print("depth histogram (depth:count) first/last:", sorted(h.items())[:5], sorted(h.items())[-5:])
