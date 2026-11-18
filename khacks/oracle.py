"""Independent exhaustive enumeration: no imports from the CP-SAT engine."""
from itertools import product

def compositions(total, n):
    if n == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for rest in compositions(total - first, n - 1):
                yield (first,) + rest

def enumerate_feasible(case):
    caps = case['capacities']; rows = []
    for r, qty in enumerate(case['accepted']):
        choices = []
        for vector in compositions(qty, len(caps)):
            if any(vector[j] and not case['eligible'][r][j] for j in range(len(caps))):
                continue
            if any(vector[j] != v for rr, j, v in case.get('pins', []) if rr == r):
                continue
            choices.append(vector)
        rows.append(choices)
    feasible = []
    for allocation in product(*rows):
        totals = [sum(row[j] for row in allocation) for j in range(len(caps))]
        if all(t <= c for t, c in zip(totals, caps)):
            feasible.append((allocation, totals))
    return feasible

def oracle_result(case):
    fs = enumerate_feasible(case)
    if not fs:
        return {'state': 'CONFLICTED', 'bounds': None}
    bounds = [[c - max(t[j] for _,t in fs), c - min(t[j] for _,t in fs)]
              for j,c in enumerate(case['capacities'])]
    return {'state': 'BOUNDED' if any(a != b for a,b in bounds) else 'RESOLVED', 'bounds': bounds}
