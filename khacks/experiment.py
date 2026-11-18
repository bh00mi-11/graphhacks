"""Bounded synthetic clarification experiment; not an ERP or market validation."""
import argparse
import copy
import json
import os
from pathlib import Path
from .engine import solve, target_decision, choose_question


def episodes():
    """Public deterministic fixtures. Answers are withheld from policy context only.

    These are development cases, not an unseen benchmark. Model contamination and
    fixture-specific overfitting are not measured.
    """
    for k in range(24):
        small, big = 1 + k % 2, 3 + (k // 2) % 3
        total = small + big
        case = dict(capacities=[total, total], accepted=[small, big],
                    eligible=[[True, True], [True, True]], pins=[], target=1)
        answers = ([small, 0], [0, big], [small, big], [0, 0],
                   [small, big // 2], [0, big // 2])[k % 6]
        yield dict(id=f"development-{k+1:02}", case=case, answers=answers,
                   expected="FULFILLED" if sum(answers) == total else "NOT_FULFILLED")


def context(case, known):
    """Only observable records, solver outputs and candidate question IDs."""
    result = solve(case)
    candidates = [r for r in range(len(case['accepted']))
                  if r not in known and case['eligible'][r][case['target']]]
    return dict(case=copy.deepcopy(case), solver=result,
                candidate_receipts=candidates,
                decision=target_decision(case, result))


def run_episode(episode, policy, budget=2):
    case = copy.deepcopy(episode['case'])
    known, trace = set(), []
    failure = None
    for _ in range(budget):
        visible = context(case, known)
        if visible['decision'] != 'UNRESOLVED':
            break
        if not visible['candidate_receipts']:
            break
        try:
            choice = policy(visible)
            if type(choice) is not int or choice not in visible['candidate_receipts']:
                raise ValueError('policy selected an invalid or repeated receipt')
        except Exception as exc:
            # Do not log provider exception bodies: they may contain request details.
            failure = type(exc).__name__
            break
        before = visible['solver']['bounds']
        answer = episode['answers'][choice]
        case['pins'].append([choice, case['target'], answer])
        known.add(choice)
        trace.append(dict(receipt=choice, reviewed_synthetic_answer=answer,
                          before=before, after=solve(case)))
    result = solve(case)
    decision = target_decision(case, result)
    return dict(id=episode['id'], decision=decision, expected=episode['expected'],
                correct=decision == episode['expected'] and failure is None,
                questions=len(trace), failure=failure, trace=trace)


def fixed(visible):
    return visible['candidate_receipts'][0]


def heuristic(visible):
    known = set(range(len(visible['case']['accepted']))) - set(visible['candidate_receipts'])
    return choose_question(visible['case'], known, True)


def llm_policy(client, model, calls):
    def select(visible):
        response = client.chat.completions.create(
            model=model, temperature=0,
            messages=[{'role':'system', 'content':
                'Choose the one receipt allocation to clarify next to establish '
                'whether the target PO is fulfilled. Use observable evidence only. '
                'Call ask_allocation with a candidate receipt index. You cannot '
                'change quantities or approve a decision.'},
                {'role':'user', 'content':json.dumps(visible)}],
            tools=[{'type':'function','function':{
                'name':'ask_allocation','description':'Request reviewed allocation evidence.',
                'parameters':{'type':'object','properties':{
                    'receipt':{'type':'integer','enum':visible['candidate_receipts']}},
                    'required':['receipt'],'additionalProperties':False}}}],
            tool_choice={'type':'function','function':{'name':'ask_allocation'}})
        tool_calls = response.choices[0].message.tool_calls or []
        if len(tool_calls) != 1 or tool_calls[0].function.name != 'ask_allocation':
            raise ValueError('expected exactly one allowed tool call')
        arguments = json.loads(tool_calls[0].function.arguments)
        if set(arguments) != {'receipt'}:
            raise ValueError('unexpected tool arguments')
        calls.append(dict(model=response.model, tool='ask_allocation',
                          arguments=arguments,
                          usage=response.usage.model_dump() if response.usage else None))
        return arguments['receipt']
    return select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-llm', action='store_true')
    parser.add_argument('--accept-api-cost', action='store_true')
    parser.add_argument('--model', default=os.getenv('SAHIAAYA_AGENT_MODEL'))
    parser.add_argument('--limit', type=int, default=24)
    parser.add_argument('--output', type=Path, default=Path('khacks-results.json'))
    args = parser.parse_args()
    if not 1 <= args.limit <= 24:
        parser.error('--limit must be 1..24')
    policies = {'fixed':fixed, 'adaptive_heuristic':heuristic}
    calls = []
    if args.real_llm:
        if not args.accept_api_cost or not args.model or not os.getenv('OPENAI_API_KEY'):
            parser.error('real mode requires --accept-api-cost, --model and OPENAI_API_KEY')
        from openai import OpenAI
        client = OpenAI(timeout=45.0, max_retries=0)
        policies['real_llm'] = llm_policy(client, args.model, calls)
    cases = list(episodes())[:args.limit]
    outcomes = {name:[run_episode(case, policy) for case in cases]
                for name, policy in policies.items()}
    report = dict(synthetic=True, suite='public_development_cases',
                  real_llm_requested=args.real_llm, requested_model=args.model,
                  max_questions_per_episode=2, results=outcomes, model_calls=calls,
                  summary={name:dict(cases=len(rows), correct=sum(r['correct'] for r in rows),
                      questions=sum(r['questions'] for r in rows),
                      failures=sum(r['failure'] is not None for r in rows))
                      for name, rows in outcomes.items()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    if any(r['failure'] for rows in outcomes.values() for r in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
