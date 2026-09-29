# Playbook

How I work a customer data problem on Databricks, organised around what the interview assesses. Each page draws on the exercises, case studies and repo notes, and links to the evidence.

| Page | Covers | Criterion |
|---|---|---|
| [00 Operating loop](00-operating-loop.md) | Frame → inspect → decompose → slice → verify → harden → scale → explain → ship; working with teammates | all |
| [01 Computational thinking](01-computational-thinking.md) | Grain first; the four questions per step; 15 transformation patterns (executed); worked decompositions | Computational thinking |
| [02 Code stewardship](02-code-stewardship.md) | Reading unfamiliar code (the method used on six repos); smells in data code; explaining execution under the hood; review checklist | Code stewardship |
| [03 AI stewardship](03-ai-stewardship.md) | Prompt skeleton; Extract-Don't-Generate; three levels of evaluation; red flags; the AI-error catalogue from these repos; recovery loop | AI stewardship |
| [04 Resilience and debugging](04-resilience-and-debugging.md) | The debug loop; row-count ledger; error signatures (reproduced); habits; bounded effort and escalation | Resilience |
| [05 Execution and scaling](05-execution-and-scaling.md) | Mental model; measured lab results; 10×/100× checklist; Delta layout; streaming state; hash collisions | Execution / scaling |
| [06 Business translation](06-business-translation.md) | Explanation shape; technical → business translations; tailoring to the listener; quantifying | Business justification |
| [07 NULL semantics](07-null-semantics.md) | Three-valued logic, verified table, patterns, how to find NULL bugs | Code stewardship / resilience |

Runnable companions: [`patterns_demo.py`](patterns_demo.py) (every idiom in page 01) and [`error_signatures_demo.py`](error_signatures_demo.py) (the error zoo behind page 04). Run them after `pip install -r exercises/requirements.txt`.
