# Solving customer problems with code on Databricks: study notes

Notes from studying six `databricks-solutions` repositories, written to prepare for working through real customer data problems with code: live, alongside teammates, with the Databricks Assistant, and explaining everything in business terms.

What's here isn't a summary of the repos. It's what I'd **do** with a customer, backed by code I ran:

- **[Playbook](playbook/)**: how I work a problem, organised by the four things being assessed.
- **[Exercises](exercises/)**: five runnable, customer-shaped problems (PySpark 4.0.1 + Delta 4.0.0), each with tests and a walkthrough.
- **[Case studies](case-studies/)**: real bugs found by reading the repos and proved by running them, including my own mistakes.
- **[Repo notes](repos/)**: one page per repo: how it works, what to steal, what's wrong, how to explain it.
- **[Cheatsheets](cheatsheets/)**: patterns, system-table checks, platform fundamentals, nine pipeline failure modes with ready-made prompts, and a question bank.
- **[Appendix](appendix/deep-read-reports/)**: the raw deep-read reports, with a list of what I re-verified in each.

## Where to look for each criterion

| Criterion | The question | Start here | Proof |
|---|---|---|---|
| **Computational thinking** | Can you break a messy problem into a logical sequence of transformations? | [playbook/01](playbook/01-computational-thinking.md) | [Exercise 01](exercises/ex01_messy_orders_medallion/WALKTHROUGH.md), [Exercise 02](exercises/ex02_scd2_merge/WALKTHROUGH.md), [`patterns_demo.py`](playbook/patterns_demo.py) |
| **Code stewardship** | Can you explain what your code does under the hood, and reason about code you didn't write? | [playbook/02](playbook/02-code-stewardship.md), [playbook/05](playbook/05-execution-and-scaling.md) | [Exercise 03](exercises/ex03_execution_and_scaling/WALKTHROUGH.md), [case 07](case-studies/07-lakeflow-delta-join-alias-parsing.md), [debug kata](exercises/ex05_debug_kata/DEBUGGING_LOG.md) |
| **AI stewardship** | Can you prompt the Assistant well, evaluate its output, and catch it when it's wrong? | [playbook/03](playbook/03-ai-stewardship.md) | The AI-error catalogue; [consort](repos/consort.md), [vibe-coding](repos/vibe-coding-workshop-template.md) |
| **Resilience** | How do you navigate bugs and the unknown? | [playbook/04](playbook/04-resilience-and-debugging.md) | [case 06: 15 near-misses](case-studies/06-near-misses-and-false-positives.md), [`error_signatures_demo.py`](playbook/error_signatures_demo.py) |
| Business justification | Can you justify your logic in business terms? | [playbook/06](playbook/06-business-translation.md) | "How I'd explain it" in every case study and repo note |

## Headline findings

| Finding | Where | Status |
|---|---|---|
| lakeflow_framework decides which side of a LEFT join to keep from the **text order** of the join condition: `a = b` keeps all customers, `b = a` drops two-thirds | [case 07](case-studies/07-lakeflow-delta-join-alias-parsing.md) | CONFIRMED with the framework's real classes |
| lakeflow_framework's wheel can't be built, can't be imported once built, and its tests can't see either fault; a three-line patch fixes all three | [case 01](case-studies/01-lakeflow-packaging-three-stacked-faults.md) | CONFIRMED, patch verified |
| NULL three-valued logic leaks rows through a quarantine predicate, and the same class of bug appears in WAF (fixed) and in my kata | [case 02](case-studies/02-null-semantics-in-quarantine-predicates.md), [playbook/07](playbook/07-null-semantics.md) | CONFIRMED |
| Seven fail-open patterns across four repos: errors that become success signals or silent "repairs" | [case 03](case-studies/03-fail-open-patterns.md) | CONFIRMED (per row) |
| AI guidance itself contains errors an assistant would copy faithfully: arbitrary dedupe, an "SCD2" that isn't, an eval gate that always passes, a fuzzy column fix that turns `customer_name` into `customer_id` | [playbook/03](playbook/03-ai-stewardship.md#6-the-ai-error-catalogue-found-in-these-repos-own-ai-guidance-or-ai-built-code) | CONFIRMED (source or execution) |
| A containment price join silently drops usage that spans a price change or has no price | [case 08](case-studies/08-price-join-containment-vs-point-in-time.md) | Mechanics CONFIRMED; real-world size data-dependent |
| A Delta DataFrame defined before a write sees the write, and `.cache()` doesn't prevent it | [case 04](case-studies/04-lazy-evaluation-meets-mutable-tables.md) | CONFIRMED |

## Conventions

- **CONFIRMED:** reproduced by execution (script linked) or read at source (stated as such).
- **SUSPECTED:** consistent with the code, but the decisive run needs a Databricks workspace; always stated together with the cheapest test that would settle it.
- **REFUTED:** looked like a bug and wasn't. Kept on purpose ([case 06](case-studies/06-near-misses-and-false-positives.md)).
- Repos were read at fixed commits (listed in [repos/](repos/)). Findings may since have been fixed upstream.

## Verification status

- **Exercises:** `48 passed, 9 xfailed` in a fresh venv built only from [`exercises/requirements.txt`](exercises/requirements.txt) (Python 3.11, OpenJDK 21, PySpark 4.0.1, delta-spark 4.0.0, pandas 2.3.3). The 9 xfails are the debug kata's buggy implementation, which must fail.
- **Evidence scripts** in [`case-studies/evidence/`](case-studies/evidence/) and the two playbook demos were run on the same stack; outputs are quoted where they're used.
- **Not available here:** a Databricks workspace. Anything that depends on Databricks-only behaviour (SDP runtime semantics, Genie, system tables on a live account, the Assistant itself) is marked SUSPECTED or labelled as field knowledge or repo documentation.

## Run it

```bash
cd exercises
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q -rx                                   # all five exercises
python ../playbook/patterns_demo.py             # the transformation idioms
python ../playbook/error_signatures_demo.py     # the error zoo
python ../case-studies/evidence/lazy_snapshot.py
```

## The six repositories

| Repo | What it is |
|---|---|
| [lakeflow_framework](repos/lakeflow_framework.md) | Metadata-driven Spark Declarative Pipelines |
| [vibe-coding-workshop-template](repos/vibe-coding-workshop-template.md) | Agent skills for AI-assisted delivery of governed data products |
| [consort](repos/consort.md) | A deterministic harness around AI coding agents, on Lakebase branches |
| [databricks-waf](repos/databricks-waf.md) | A Well-Architected assessment app on system tables |
| [technical-services-solutions](repos/technical-services-solutions.md) | The field team's platform, governance, BI-migration and CI/CD accelerators |
| [starter-journey](repos/starter-journey.md) | The field team's runbook from an empty account to a governed platform |
