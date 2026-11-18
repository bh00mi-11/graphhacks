import copy
import random
import pytest
from khacks.engine import solve, approval_stale
from khacks.oracle import oracle_result
from khacks.experiment import episodes, context, run_episode, fixed, heuristic


def test_worked_example_and_new_evidence():
    case = dict(capacities=[300,200], accepted=[240,150],
                eligible=[[True,True],[False,True]], pins=[])
    assert solve(case)['bounds'] == [[60,110],[0,50]]
    case['pins'] = [[0,1,50]]
    assert solve(case)['bounds'] == [[110,110],[0,0]]


@pytest.mark.parametrize('seed', range(50))
def test_generated_bounds_against_separate_enumerator(seed):
    rng = random.Random(seed)
    case = dict(capacities=[rng.randint(1,6) for _ in range(3)],
                accepted=[rng.randint(0,4) for _ in range(3)],
                eligible=[[bool(rng.randrange(2)) for _ in range(3)] for _ in range(3)])
    actual = solve(case)
    assert {k:actual[k] for k in ('state','bounds')} == oracle_result(case)


def test_timeout_does_not_claim_proven_bounds():
    assert solve(next(episodes())['case'], time_limit=0)['bounds'] is None


def test_conflicting_pins():
    case = next(episodes())['case']
    case['pins'] = [[0,1,0],[0,1,1]]
    assert solve(case)['state'] == 'CONFLICTED'


@pytest.mark.parametrize('mutation', ['negative','bool','dimensions','pin','target'])
def test_invalid_inputs(mutation):
    case = next(episodes())['case']
    if mutation == 'negative': case['accepted'][0] = -1
    if mutation == 'bool': case['capacities'][0] = True
    if mutation == 'dimensions': case['eligible'][0] = [True]
    if mutation == 'pin': case['pins'] = [[900,1,0]]
    if mutation == 'target': case['target'] = -1
    with pytest.raises(ValueError): solve(case)


def test_answer_is_not_visible_to_policy():
    episode = next(episodes())
    visible = context(episode['case'], set())
    assert 'answers' not in visible and 'expected' not in visible
    seen = []
    def spy(v):
        seen.append(copy.deepcopy(v))
        return fixed(v)
    result = run_episode(episode, spy)
    assert result['correct']
    assert all('answers' not in v and 'expected' not in v for v in seen)


def test_illegal_tool_selection_fails_closed():
    result = run_episode(next(episodes()), lambda _: -1)
    assert result['failure'] == 'ValueError'
    assert not result['correct'] and not result['trace']


def test_provider_failure_stays_in_denominator():
    def fail(_): raise RuntimeError('fake provider error')
    result = run_episode(next(episodes()), fail)
    assert result['failure'] == 'RuntimeError' and not result['correct']


@pytest.mark.parametrize('policy', [fixed,heuristic])
def test_policies_resolve_public_cases(policy):
    results = [run_episode(case, policy) for case in episodes()]
    assert all(r['correct'] for r in results)


def test_changed_dependency_invalidates_approval():
    approval = {'dependencies':{'DN-77':1,'rule':1}}
    assert not approval_stale(approval, {'DN-77':1,'rule':1})
    assert approval_stale(approval, {'DN-77':2,'rule':1})
    assert approval_stale(approval, {'rule':1})
