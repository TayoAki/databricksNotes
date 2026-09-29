# 06. Business translation: justifying logic in business terms

> **What's being assessed:** "Be prepared to explain your code as if you were talking to a customer or internal stakeholder. Can you justify your logic in business terms?"

## 1. The shape of a good explanation

```
WHAT CHANGED      in their words, about their numbers or their process
WHY IT MATTERS    the decision or risk it affects, with a number if I have one
WHAT WE DID       one sentence, no jargon
HOW YOU'LL KNOW   the check that proves it, and what they'll see if it ever breaks
```

Example (Exercise 01):
> "Finance and Ops were both right about different things. Ops counted every order version, and Finance counted cancelled orders it shouldn't have. One customer was also listed twice in the master file, which inflated their revenue by 7%. We now keep one version of each order (the latest by when it happened, not when it arrived), exclude cancellations, and check every day that joining customer data doesn't change the order count. If it ever does, the job stops and tells us which customer is duplicated."

## 2. Translating technical concepts

| Technical concept | Business translation | The risk it manages |
|---|---|---|
| Grain | "One row means one order" | Counting things twice |
| Deduplicate latest per key | "We keep the most recent version of each order, by when it happened" | Stale or double-counted records |
| Event time vs arrival time (`sequence_by`) | "A correction that arrives late but describes an earlier state doesn't overwrite newer information" | An older update silently undoing a newer one |
| Quarantine with reasons | "Bad records go to a review queue with a reason, instead of disappearing or stopping the whole pipeline" | Silent data loss; one bad file blocking the business |
| NULL-safe rules | "Every rule says what a *missing* value means" | Records with blanks slipping through checks |
| Idempotent rerun | "Running it twice gives the same answer as running it once" | Duplicates after a retry |
| Fan-out guard | "We check that adding customer details doesn't multiply orders" | Inflated revenue from duplicate master data |
| SCD2 / point-in-time | "We can report by the segment a customer was in *at the time of the sale*, not just today" | Restating history when attributes change |
| Semi-additive measure | "Balances are taken at month end, not added up across days" | Summing daily snapshots counts the same balance once per day (in [the demo](01-computational-thinking.md#the-idioms-as-executed): 430 instead of 160) |
| Watermark | "How long we wait for late data before closing the books on a time window" | Either late data is lost or results are delayed; a business choice |
| Checkpoint | "The pipeline remembers what it has already processed" | Reprocessing (cost) or gaps (missing data) |
| Broadcast join | "Small reference tables are copied to every worker so the big table never moves" | Cost growing faster than the data |
| Skew | "One very large customer makes one worker do most of the work" | A job that's slow for no visible reason |
| Liquid clustering / data skipping | "Data is organised so queries read only the files they need" | Paying to scan data you don't use |
| Unity Catalog grants to groups | "Access follows your org chart: joiners and leavers are handled by HR systems" | Orphaned access; manual, unauditable grants |
| ABAC / column masks | "Sensitive fields are masked automatically wherever they appear" | A new table leaking PII before anyone writes a rule |
| Metric view | "Revenue is defined once, so the dashboard, the chatbot and the analyst all show the same number" | "ARR is $2.5M in one meeting and $2.8M in the next" |
| OBO (on-behalf-of) | "The app sees exactly what you're allowed to see, no more" | Users seeing data "through admin eyes" |
| Fail-closed / "not measured never becomes pass" | "If we couldn't check it, we say so, instead of calling it fine" | False confidence in an audit or a score |
| DAB + CI/CD | "Every change is reviewed and promoted the same way; nobody edits production by hand" | Key-person risk; unrepeatable deploys |
| Tags + budgets from day zero | "You'll always be able to say who spent what" | "Retrofitting attribution is not a thing" |

## 3. Tailor it to the listener

| Listener | They care about | Lead with |
|---|---|---|
| Executive / CIO | Risk, cost, speed, trust | The decision it enables and the risk removed ("one revenue number") |
| Finance | Reconciliation, auditability, definitions | The definition and the reconciliation check ("ties to the ledger to the cent, daily") |
| Data engineer | How it runs, fails and scales | Grain, incrementality, failure modes, the plan |
| Analyst / BI | Can I trust and find it? | Definitions, freshness, where the metric lives, what "Unknown" means |
| Security / governance | Who can see what, and proof | Identity model, grants, masks, audit tables |
| Internal stakeholder (account team) | Fit, risk, upsell, effort | What it solves, what it doesn't, what the customer must own |

## 4. Quantify whenever possible

Numbers make a technical point land, and every one of these came from a check I ran or read at source:
- "The naive join overstated revenue by **7.2%** (2379.48 vs 2219.49), all from one duplicated customer." (Exercise 01)
- "A filter written the obvious way kept **0 of 6,969** statements, when only the **3,773** that were the app's own should have been excluded." (databricks-waf's own comment)
- "Filtering the history table in the wrong order reported **6.1 million** live clusters where **135 thousand** existed: 45×." (WAF)
- "Trusting the serverless flag alone understated serverless spend by **$12,770 of a $16,190** bill." (WAF)
- "Swapping two words in a join condition dropped **two-thirds** of customers." ([case 07](../case-studies/07-lakeflow-delta-join-alias-parsing.md))

## 5. Explaining a trade-off honestly

- **Name the choice as a business choice.** "Reporting revenue by the customer's segment *today* is simpler; reporting it by the segment *at the time of sale* needs history. Which does Finance expect?"
- **Say what you gave up.** "Waiting 30 minutes for late data means the last half hour isn't on the dashboard until the next run."
- **Say what would change your mind.** "If late data turns out to arrive up to a day later, we'd switch this to a daily restatement."

## 6. Phrases that build trust

- "Here's how you'll be able to check it yourself."
- "This is an assumption; tell me if it's wrong."
- "We found this by testing, not by reading: here's the number before and after."
- "What we don't measure yet is X; until then, treat Y as an estimate."
