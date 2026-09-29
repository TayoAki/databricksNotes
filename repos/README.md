# Repo notes

One page per repo studied (all from `github.com/databricks-solutions`, read at the commits listed). Each covers: what it is for a customer, how it executes, patterns worth stealing, status-tagged findings, how it scales, how I'd explain it to three audiences, interview angles, and the AI-stewardship lesson.

| Repo | In one line | Steal this | Headline finding |
|---|---|---|---|
| [lakeflow_framework](lakeflow_framework.md) @ `0e8d0ca` | Metadata-driven Spark Declarative Pipelines: JSON/YAML specs → SDP objects | Framework/pipeline bundle split; `src/local` sparse overlay; pinned flow names; the streaming-DWH pattern | Join direction decided by the text order of the condition ([case 07](../case-studies/07-lakeflow-delta-join-alias-parsing.md)); the wheel can't be built or imported ([case 01](../case-studies/01-lakeflow-packaging-three-stacked-faults.md)) |
| [vibe-coding-workshop-template](vibe-coding-workshop-template.md) @ `a26c6d0` | ~90 agent skills that guide an AI through a governed data product, stage by stage | Extract-Don't-Generate; one conversation per stage; proof-of-reading gates; bounded autonomy | Its own skills contain AI errors: an arbitrary dedupe, an "SCD2" that isn't, an eval gate that always passes |
| [consort](consort.md) @ `61b3a48` | A deterministic state machine around AI coding agents, building on Lakebase branches | Pure router + effects seam; stall detector; one informed retry; fail-closed gates that check evidence | The repair-loop bound resets when a repair adds a file |
| [databricks-waf](databricks-waf.md) @ `e765461` | A Well-Architected assessment app built on system tables | "Not measured never becomes pass"; score ranges; rank-then-filter SCD2; point-in-time pricing with coverage | Its own 45× SCD2 bug, measured and fixed; a few remaining pass-on-empty leaks |
| [technical-services-solutions](technical-services-solutions.md) @ `41fa465` | The field team's accelerators: Terraform, ABAC, Lakeflow Connect, metric views, PBI → AI/BI, CI/CD | Self-assuming IAM role; ABAC with pure masks; `SELECT * FROM (<sql>) LIMIT 0` validation | LLM "repair" swaps `unit_cost` for `unit_count`; published dashboards run as the app's service principal |
| [starter-journey](starter-journey.md) @ `ac21559` | The field team's runbook from an empty account to a governed, cost-visible, CI/CD-ready platform | Decisions that are expensive to change; prompt + checklist + fallback; the AI Platform Kit prompt | A freshness check that trusts a typo'd year; a price join that drops rows |

Raw deep-read reports, with a list of what I re-verified in each: [`appendix/deep-read-reports/`](../appendix/deep-read-reports/).
