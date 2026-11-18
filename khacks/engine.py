"""Executable prototype core. CP-SAT bounds, evidence gates, version-bound approvals."""
import copy
from ortools.sat.python import cp_model

def validate(case):
    """Reject malformed structured inputs before constructing solver variables."""
    caps, quantities, eligible = case['capacities'], case['accepted'], case['eligible']
    if not caps or len(caps) > 10 or len(quantities) > 30:
        raise ValueError('experiment supports 1..10 POs and at most 30 receipts')
    if any(type(v) is not int or not 0 <= v <= 1000000 for v in caps + quantities):
        raise ValueError('quantities must be bounded nonnegative integer pieces')
    if len(eligible) != len(quantities) or any(
        len(row) != len(caps) or any(type(v) is not bool for v in row) for row in eligible):
        raise ValueError('eligibility dimensions or types are invalid')
    for pin in case.get('pins', []):
        if len(pin) != 3 or any(type(v) is not int for v in pin):
            raise ValueError('invalid allocation pin')
        r, j, v = pin
        if not 0 <= r < len(quantities) or not 0 <= j < len(caps) or not 0 <= v <= quantities[r]:
            raise ValueError('allocation pin out of range')
    target = case.get('target', 0)
    if type(target) is not int or not 0 <= target < len(caps):
        raise ValueError('target out of range')


def solve(case, time_limit=3.0):
    validate(case)
    if not 0 <= time_limit <= 30:
        raise ValueError('time limit must be between zero and 30 seconds')
    caps=case['capacities']; accepted=case['accepted']; eligible=case['eligible']
    model=cp_model.CpModel()
    x=[[model.new_int_var(0, qty if eligible[r][j] else 0, f'r{r}_p{j}')
        for j in range(len(caps))] for r,qty in enumerate(accepted)]
    for r,qty in enumerate(accepted): model.add(sum(x[r]) == qty)
    totals=[sum(x[r][j] for r in range(len(accepted))) for j in range(len(caps))]
    for j,cap in enumerate(caps): model.add(totals[j] <= cap)
    for r,j,v in case.get('pins',[]): model.add(x[r][j] == v)
    bounds=[]; statuses=[]
    for j,cap in enumerate(caps):
        extrema=[]
        for maximize in [True,False]:
            if maximize: model.maximize(totals[j])
            else: model.minimize(totals[j])
            solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=time_limit
            solver.parameters.num_search_workers=1; solver.parameters.random_seed=20261117
            status=solver.solve(model); statuses.append(solver.status_name(status))
            if status == cp_model.INFEASIBLE:
                return {'state':'CONFLICTED','bounds':None,'solver_statuses':statuses}
            if status != cp_model.OPTIMAL:
                return {'state':'INCOMPLETE','bounds':None,'solver_statuses':statuses}
            extrema.append(cap-int(solver.value(totals[j])) if accepted else cap)
        bounds.append(extrema)
    return {'state':'BOUNDED' if any(a!=b for a,b in bounds) else 'RESOLVED',
            'bounds':bounds,'solver_statuses':statuses}

def prepare(raw):
    """Inputs are structured fixtures, not OCR output. No unknown-to-zero coercion."""
    if not raw.get('complete',False): return {'state':'BLOCKED','reason':'source completeness not established'}
    if not raw.get('po_active',True): return {'state':'CONFLICTED','reason':'cancelled PO'}
    if raw.get('supplier_eligible') is None: return {'state':'BLOCKED','reason':'supplier eligibility unknown'}
    if raw.get('supplier_eligible') is False: return {'state':'CONFLICTED','reason':'supplier mismatch'}
    if raw.get('unit') != 'piece': return {'state':'BLOCKED','reason':'conversion not established'}
    seen={}; accepted=[]; eligible=[]
    for rec in raw['records']:
        if rec['kind'] in ['promise','dispatch_claim']: continue
        if rec.get('received') is None or rec.get('rejected') is None:
            return {'state':'BLOCKED','reason':'quantity unknown'}
        if rec.get('reviewed') is not True:
            return {'state':'BLOCKED','reason':'required receipt verification absent'}
        if not 0 <= rec['rejected'] <= rec['received']:
            return {'state':'CONFLICTED','reason':'invalid rejection quantity'}
        signature=(rec['received'],rec['rejected'],tuple(rec['eligible']))
        if rec['id'] in seen:
            if seen[rec['id']] != signature:
                return {'state':'CONFLICTED','reason':'conflicting duplicate receipt'}
            continue
        seen[rec['id']]=signature
        accepted.append(rec['received']-rec['rejected']); eligible.append(rec['eligible'])
    case={'capacities':raw['capacities'],'accepted':accepted,'eligible':eligible,'pins':[]}
    if raw.get('allocation_claim'):
        claim=raw['allocation_claim']
        if claim.get('corroborated'): case['pins']=claim['pins']
        # Otherwise the assertion is retained as a claim; it does not alter allocation facts.
    return {'state':'READY','case':case,'unique_receipts':len(seen)}

def evaluate(raw):
    prepared=prepare(raw)
    if prepared['state']!='READY': return prepared
    return {**solve(prepared['case']), 'unique_receipts':prepared['unique_receipts']}

def target_decision(case,result):
    if result['state'] in ['BLOCKED','CONFLICTED','INCOMPLETE']: return 'ABSTAIN'
    lo,hi=result['bounds'][case.get('target',1)]
    if hi==0: return 'FULFILLED'
    if lo>0: return 'NOT_FULFILLED'
    return 'UNRESOLVED'

def choose_question(case,known,adaptive):
    candidates=[r for r in range(len(case['accepted'])) if r not in known and case['eligible'][r][case['target']]]
    if not candidates:return None
    if not adaptive:return candidates[0]
    current=solve(case);lo,hi=current['bounds'][case['target']];width=hi-lo
    scores=[]
    for r in candidates:
        reductions=[]; decisive=0; feasible=0
        for answer in range(case['accepted'][r]+1):
            test=copy.deepcopy(case);test.setdefault('pins',[]).append([r,case['target'],answer]);out=solve(test)
            if out['state']=='CONFLICTED':continue
            if out['bounds'] is None:continue
            feasible+=1;a,b=out['bounds'][case['target']];reductions.append(width-(b-a))
            decisive+=target_decision(test,out)!='UNRESOLVED'
        # Worst-case reduction, then number of decisive branches, then stable input order.
        # Branch counts are NOT calibrated probabilities and do not inspect the hidden answer.
        scores.append((min(reductions) if reductions else -1,decisive,-r,r))
    return max(scores)[-1]

def investigate(case,truth,adaptive,budget=2):
    c=copy.deepcopy(case);known=set();trace=[];result=solve(c)
    for _ in range(budget):
        if target_decision(c,result)!='UNRESOLVED':break
        r=choose_question(c,known,adaptive)
        if r is None:break
        before=result['bounds'][c['target']];answer=truth[r]
        c.setdefault('pins',[]).append([r,c['target'],answer]);known.add(r);result=solve(c)
        after=result.get('bounds');after=after[c['target']] if after else None
        trace.append({'question_receipt':r,'reviewed_synthetic_answer':answer,'before':before,'after':after})
    return {'decision':target_decision(c,result),'questions':len(trace),'trace':trace}

def approval_stale(approval,current):
    return any(current.get(k)!=v for k,v in approval['dependencies'].items())
