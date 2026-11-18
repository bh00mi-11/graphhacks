# SahiAaya Resolve — K! Hacks experiment

This is a separate manufacturing investigation experiment built on the Graph Hacks
repository. Existing Graph Hacks app/routes are unchanged. This folder is NOT a
finished manufacturing UI, ERP integration, OCR pipeline or production approval system.
Original Graph Hacks work must be disclosed wherever prior work is relevant.

## What works here

- Integer allocation bounds from OR-Tools CP-SAT; non-optimal solves abstain.
- Reviewed synthetic allocations narrow bounds; contradictory allocations conflict.
- Fixed question order and adaptive deterministic question selection use the same solver.
- Optional real LLM selects a bounded clarification tool. It cannot edit quantities,
  approve a decision or release payment. Tool/API failures remain in results.
- Separate exhaustive enumerator checks small generated allocation cases.
- Model request context excludes fixture answers and expected outcomes.

## Install and run (from repo root; Python 3.11+)

```sh
python -m venv .venv-khacks
# Linux/macOS:
. .venv-khacks/bin/activate
# Windows PowerShell instead:
# .\.venv-khacks\Scripts\Activate.ps1
python -m pip install -r khacks/requirements.txt
python -m pytest -q khacks/tests
python -m khacks.experiment --output khacks/results/local.json
```

### Real-model comparison

Set `OPENAI_API_KEY` locally using your terminal or secret manager; never commit it
or paste it into chat. Set `OPENAI_BASE_URL` only if using a trusted OpenAI-compatible
provider. Choose an actual available model ID from that provider's documentation.
The provider must support Chat Completions function calling and forced tool choice.
Provider compatibility has not been live-tested in this environment.

```sh
python -m khacks.experiment --real-llm --accept-api-cost --model YOUR_MODEL_ID --limit 2 --output khacks/results/real-smoke.json
# After checking the small run and API cost:
python -m khacks.experiment --real-llm --accept-api-cost --model YOUR_MODEL_ID --limit 24 --output khacks/results/real-full.json
```

At most two API calls per episode, no automatic retries. Up to 48 requests for 24
cases. Model version, tool arguments, usage and failures are recorded. No hidden
chain of thought is requested or recorded. Review outputs before publishing.

## Actual local results

New extension tests: 64 passed locally. Existing Graph Hacks integration and live
FalkorDB gates were not rerun because this extension adds no original-app changes.

`results/deterministic.json`: 24 public synthetic development episodes.
Fixed policy: 24/24 correct, 36 clarification requests.
Adaptive heuristic: 24/24 correct, 32 clarification requests.
These results establish neither LLM benefit nor human time saved.
Real LLM evaluation was NOT run: this environment has no configured model key.
The new runner's provider interoperability therefore remains unverified.

## Evaluation limitations

These fixtures repeat a narrow two-PO family, all resolve within two complete,
reviewed oracle answers. Answers are hidden from the model prompt, but fixtures
are public and are not an unseen holdout. This is a development smoke experiment,
not a strong agentic benchmark. Do not sell 24/24 as manufacturing accuracy.
The independent enumerator is separately implemented by the same author, not an
independent human audit. Bounds assume complete eligibility, accepted integer
pieces, no over-receipt and complete PO coverage. They are not payable amounts.
The solver limit per objective is three seconds. Adaptive scoring enumerates
possible answers and is only suitable for small fixtures, not large workloads.
No auth, supplier sending, real document extraction or persistent approvals added.
Do not expose the existing unauthenticated demo publicly with real documents.

## Remaining code work, in order

1. Schema-validated PO, goods-receipt, inspection and source-linked evidence imports.
   Receipt evidence must be buyer-reviewed; a supplier dispatch email is not receipt.
2. Persistent event ledger with tenant isolation, source/field versions, corrections,
   monetary units and duplicate detection. Keep credits separate from physical goods.
3. Reviewer-controlled allocation evidence, unknown/partial/contradictory replies,
   timeouts, budget termination and human escalation in an actual investigation loop.
4. Dependency snapshots for proposals and approvals; changed evidence invalidates
   approval atomically. Current helper is an in-memory fixture only.
5. Manufacturing UI: upload -> evidence review -> bounds -> question -> proposal.
   Show RESOLVED / BOUNDED / BLOCKED / CONFLICTED / INCOMPLETE; retain source links.
6. A frozen, independently reviewed unseen test set with multiple PO sizes, missing
   records, inconsistent answers, unit conversions and irrelevant question choices.
   Compare fixed, strong heuristic and LLM under equal tool/question budgets.
7. Source verification, access control, audit retention and export; finance approval
   before any proposed payment. Tax, prior payments and contract terms are excluded.

## Apply this package to Bhoomi's existing copy

Repository: https://github.com/bh00mi-11/graphhacks
Base commit: a1a00120f688c5cefdc21c95f6c9412fdb507bc6
Published on the `khacks-resolve` branch after repository write access was enabled.
The instructions below are for applying the standalone ZIP to a fresh clone.

```sh
git clone https://github.com/bh00mi-11/graphhacks.git
cd graphhacks
git switch -c khacks-resolve
# Extract the supplied ZIP into this directory (it adds only khacks/).
git add khacks
git commit -m "Add isolated manufacturing allocation and clarification experiment"
git push -u origin khacks-resolve
```

Alternative: use `git apply --check /path/to/SahiAaya_KHacks.patch` then
`git apply /path/to/SahiAaya_KHacks.patch` instead of copying the folder.
Use exactly one method. If main changed, inspect differences before applying.
Do not merge or deploy automatically. Keep API keys outside tracked files.

AI assistance was used for this experimental extension and its tests.
