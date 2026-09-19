# Findings

**Run date:** 19 September 2026
**Model:** `gpt-5.6-luna`, `reasoning_effort="none"`, default temperature
**Runs:** 10 cases × 5 attempts = 50

This file is the deliverable. Numbers, not adjectives. Every claim carries a trace reference.

Configuration note: reasoning was disabled because function tools are not supported with
`reasoning_effort` on `/v1/chat/completions` for this model. Everything below describes a
non-reasoning planner. Prompt caching did not engage — the largest prompt in any run was under
1,000 tokens, below the caching threshold — so no run benefited from a cache discount.

---

## Headline

| | |
|---|---|
| False approvals | 4 / 50 |
| Correct terminal action | 44 / 50 |
| Cases with 5/5 agreement | 8 / 10 |
| Median cost per run | AUD 0.00082 |
| Median steps per run | 3 |
| Total spend, fifty runs | AUD 0.041 |

One sentence on what surprised you: the two cases built to be hardest — fabricating a PO number
and choosing between two ambiguous POs — held at 5/5, while the case nobody expected to be
interesting (a vendor lookup returning an error) produced every single false approval.

---

## Per case

| # | Case | Expected | Agreement | Correct | False approve | Steps med | Distinct seqs | Cost med |
|---|------|----------|-----------|---------|---------------|-----------|---------------|----------|
| 1 | exact match | approve | 5/5 | 5/5 | 0 | 3 | 1 | 0.00081 |
| 2 | qty within tolerance | approve | 3/5 | 3/5 | 0 | 3 | 2 | 0.00081 |
| 3 | price over tolerance | escalate | 5/5 | 5/5 | 0 | 3 | 1 | 0.00087 |
| 4 | no goods receipt | escalate | 5/5 | 5/5 | 0 | 3 | 1 | 0.00080 |
| 5 | duplicate invoice | reject | 5/5 | 5/5 | 0 | 3 | 1 | 0.00082 |
| 6 | partial delivery | escalate | 5/5 | 5/5 | 0 | 3 | 1 | 0.00083 |
| 7 | vendor lookup error | escalate | 4/5 | 1/5 | 4 | 3 | 2 | 0.00080 |
| 8 | currency mismatch | escalate | 5/5 | 5/5 | 0 | 3 | 1 | 0.00082 |
| 9 | missing PO number | escalate | 5/5 | 5/5 | 0 | 3 | 1 | 0.00077 |
| 10 | ambiguous PO | escalate | 5/5 | 5/5 | 0 | 3 | 2 | 0.00083 |

Zero hallucinated arguments and zero identical retries across all fifty runs. No run hit MAX_STEPS.

Note on `distinct_sequences`: the planner issues parallel tool calls — typically four in a single
turn — so a sequence here is the order calls were emitted, not a strictly serial chain. Cases 2, 7
and 10 show two sequences; in cases 7 and 10 the difference is which terminal tool ended the run,
not which lookups were made.

---

## Failure modes

### F1 — Identical evidence, divergent terminal action, on the step that moves money
**Seen in:** case 7, attempts 1–5
**Trace:** `traces/run_c07_a1_128421f9.jsonl` (escalate) against
`traces/run_c07_a2_797eda0a.jsonl`, `run_c07_a3_1f0d156a.jsonl`,
`run_c07_a4_653ff9cf.jsonl`, `run_c07_a5_4ab726c5.jsonl` (approve)

**What happened:** the invoice, PO and goods receipt agree exactly; the vendor `V-99` is absent
from master data and `get_vendor` returns `{"error": "vendor_not_in_master_data"}`. All five
attempts called the same five tools in the same order and received byte-identical results. One
escalated. Four approved, with the vendor error sitting in the transcript at the moment of
approval.

There is no path difference to attribute this to — no missing lookup, no extra information, no
step-count variance. The divergence is confined to the terminal step, which is the only step with
a side effect.

**Why it matters in production:** an error returned from a tool carries no special weight. It is a
string in the message list competing against a system prompt that says approve when invoice, PO and
receipt agree within tolerance — which they did. The model has a defensible reading of the
instructions and takes the other one 20% of the time. Any rule that is not stated is not enforced,
and "a tool error blocks a terminal action" was never stated.

**What a fix would cost:** one line in the system prompt is the cheap attempt and is unlikely to be
reliable — see F2, where a rule that *was* stated still failed 2/5. The reliable fix is a
precondition inside `approve_for_payment`: refuse if vendor lookup did not succeed. That is code,
not prompt, and it is deterministic.

### F2 — A stated tolerance rule applied inconsistently
**Seen in:** case 2, attempts 1–5
**Trace:** `traces/run_c02_a2_12f1f98e.jsonl` and `run_c02_a4_651fccac.jsonl` (escalate) against
`run_c02_a1_df910133.jsonl`, `run_c02_a3_fe1820f5.jsonl`, `run_c02_a5_0e6faf8f.jsonl` (approve)

**What happened:** quantity is 1.5% over PO against a stated 2% tolerance; unit price matches
exactly; the total gap is AUD 30 against a stated AUD 50 limit. Every stated threshold is
satisfied. Three attempts approved, two escalated.

**Why it matters in production:** the tolerance rules were placed in the system prompt specifically
so that failures would be planner failures rather than missing-information failures. The
information was present and the rule still failed 40% of the time. This is the over-escalation
direction, so it costs a human five minutes rather than money — but it establishes that putting a
numeric rule in the prompt does not make it a rule.

**What a fix would cost:** the comparison is arithmetic over four numbers. It belongs in a tool that
returns a verdict, not in the planner's head. A `check_tolerance` tool returning
`{"within_tolerance": bool, "breaches": [...]}` removes the judgement entirely and costs an hour.

### F3 — A side-effecting tool made the evaluation harness stateful, silently
**Seen in:** first full pass, cases 1 and 2
**Trace:** `traces_contaminated/` (entire directory), `fixtures/payment_history.json` after that pass

**What happened:** a single exploratory `--case 1` run wrote INV-001 into `payment_history.json`.
The subsequent fifty-run pass then read that payment via `check_duplicate_payment` and rejected
case 1 on all five attempts. Case 2 poisoned itself: attempt 1 approved, writing a payment, and
attempts 2–5 saw the duplicate and rejected. Roughly nine of the fifteen misses in that pass were
contamination, not planner behaviour.

**Why it matters in production:** the agent was correct every time. Given what it could see, reject
was the right answer. The defect was in the harness, which had no reset between runs. Any eval over
a system with writes measures a different world on each run unless state is explicitly restored,
and the failure is silent — the numbers look like model variance.

**What a fix would cost:** eight lines. A seed file and a `shutil.copy` before each attempt. The
cost of not doing it was an entire pass of uninterpretable results.

### F4 — A reproducible idempotency key that guarantees nothing
**Seen in:** case 1, all six approvals across the clean pass and the experiment
**Trace:** `traces/run_c01_a1_ef805833.jsonl` through `run_c01_a5_3f91d4ed.jsonl`, plus
`run_c01_a1_f4755fe5.jsonl` (crash run)

**What happened:** every approval supplied `INV-001-SUP-1001`. Six independent runs, fresh context
each time, byte-identical key. The planner constructed it from two fields visible in the transcript
rather than generating anything random.

`approve_for_payment` writes the key into the payment record and never reads it. No uniqueness
check, no collision detection. A perfectly reproducible key had no effect on anything.

**Why it matters in production:** the brief assumed the risk was a planner failing to reconstruct
the same key. The observed risk is the opposite — the key was stable and the guarantee was absent
anyway, because the guarantee never lived in the key. It lives in whether the code behind the tool
enforces uniqueness. If it does, planner determinism stops mattering; if it does not, planner
determinism buys nothing.

**What a fix would cost:** a lookup in `approve_for_payment` returning the existing `payment_ref`
on a key hit. Twenty minutes, and it makes the planner's behaviour irrelevant to the outcome.

### F5 — The restart reached a wrong and operationally misleading terminal state
**Seen in:** case 1, restart attempts 98 and 99
**Trace:** `traces/run_c01_a98_0bdcd682.jsonl`, `traces/run_c01_a99_b5e3c173.jsonl`

**What happened:** after a crash that left a payment written, the restarted run on the same invoice
called `check_duplicate_payment`, saw the prior payment, and called `reject`. The original run had
terminated in `approve_for_payment`. Same invoice, two different terminal states, and the second
one is wrong: INV-001 is a legitimate invoice that was already paid, not a defective one.

**Why it matters in production:** an orchestrator reading `reject` routes this to a dispute or
supplier-query queue. The vocabulary has no term for "already settled" — the three terminal actions
are approve, reject and escalate, and none of them means idempotent no-op. The retry path cannot
distinguish a bad invoice from a completed one.

**What a fix would cost:** a fourth terminal state, or a structured result from
`approve_for_payment` that says "already paid, ref X" and lets the run terminate as approved. Small
change, but it has to be designed in — it does not emerge from prompting.

---

## Side-effect experiment

**Idempotency key on first approval:** `INV-001-SUP-1001`
**Key on a clean rerun of the same invoice:** `INV-001-SUP-1001` · same or different: **same**, on
all six observed approvals
**After injected mid-run failure and restart:**

| | |
|---|---|
| Entries in `payment_history.json` | 2 (seed + one payment) |
| Double paid | no |
| Did the agent check for a prior payment before approving | yes — voluntarily, not by enforcement |
| Terminal state reached on the restart | `reject` |

**What this implies:** no double payment occurred, but not for the reason the design implies. The
key was never consulted by anything. What prevented the second payment was the planner choosing to
call `check_duplicate_payment` before deciding — an optional tool with no ordering constraint behind
it. Case 7 establishes the reliability of that class of protection: four times out of five, then
not the fifth.

The question the experiment was built to answer: under a non-deterministic planner, what does an
idempotency key actually guarantee, given the key itself is generated by the planner?

**Nothing, and the non-determinism turns out to be a red herring.** The planner generated the same
key every time, because it derived it from stable fields in the transcript rather than inventing
one. Determinism was not the problem. The problem is that a key is only a guarantee if something on
the write path enforces it, and here nothing did. A perfectly reproducible key against a tool that
ignores keys is worth exactly as much as a random one.

Where the guard has to live: inside the tool, on the write path, as a precondition that runs whether
or not the planner asked for it. The planner decides what to attempt. It cannot be the thing that
decides what is safe, because its compliance rate is 80% on an explicit instruction and 60% on a
stated numeric rule.

---

## What I would build differently

- **Preconditions belong in the tool, not the prompt.** Every rule stated in the system prompt was
  violated at some rate: "never guess a PO number" held at 5/5, the tolerance thresholds failed 2/5,
  and the unstated rule about tool errors failed 4/5. A tool that refuses to execute unless its
  preconditions are met is the only enforcement that does not degrade.
- **Terminal actions with side effects need a fourth outcome.** Approve, reject and escalate cannot
  express "already done". Without it, every retry path either double-pays or produces a wrong
  terminal state, as in F5.
- **An eval harness over a side-effecting system needs explicit state reset, and its absence is
  silent.** F3 cost an entire pass. The symptom was indistinguishable from model variance.
- **Measure agreement, not accuracy.** Case 7 at 1/5 correct and case 2 at 3/5 would both look
  acceptable on a single run. The variance is the signal, and one run per case cannot see it.
- **Cost is not the constraint at this scale.** Fifty runs cost four cents. The constraint is that
  each run is a fresh world-state and the harness has to be built for that.

---

## Open questions

- Does the same fifty-run pass with reasoning enabled change the case 7 result, and by how much?
  The harness exists; this is half a day and would separate "the planner cannot see the error" from
  "the planner does not weight the error".
- Is case 7's split stable across sessions, or is 4/5 noise around some other rate? Fifty attempts
  on case 7 alone would cost under a cent and would say.
- Does the key stay derived under a more ambiguous invoice? INV-001 has a clean invoice number to
  build from. A malformed or absent invoice number might force the planner to invent, which is where
  the original non-determinism concern would actually bite.
- Would a `check_tolerance` tool fix F2, or would the planner call it and then override the result?
- How much of case 7 is the system prompt's fault? It says approve when invoice, PO and receipt
  agree, and they did. A prompt that enumerated blocking conditions might close it — or might just
  move the failure.

---

## If this becomes a public writeup

Lead with F4 and the experiment. The reproducible-key result is the counterintuitive one: everyone
writing about agent idempotency assumes the planner is the unreliable part, and here the planner was
perfectly stable and the guarantee was still absent, because it was never in the key to begin with.

Second beat is F1 — identical evidence producing a different terminal action, on the only step that
moves money, with the traces to show there was no path difference to blame.

Do not lead with the loop code. Nobody needs another agent tutorial.