# Agent Failure Lab

A hand-written tool-calling agent over three-way invoice matching, run fifty times to find out how
it breaks. The deliverable is [FINDINGS.md](FINDINGS.md), not the code.

Every claim below has a trace file behind it in `traces/`.

---

## The question

Three-way matching is an accounts payable control: before an invoice is paid, someone checks it
against the purchase order and the goods receipt. Approve, reject, or escalate to a human.

One of those three outcomes moves money. That makes it a useful place to ask a question that mostly
goes unasked: **when a tool has a side effect and the run fails halfway through, what actually
protects you?**

The usual answer is an idempotency key. But under a non-deterministic planner the key is generated
by the model, and there is no guarantee it reconstructs the same one. Compensating actions assume a
plan you can walk backwards, and an agent has no plan — only a history.

This repo tests that.

---

## Results

Ten cases, five attempts each, `gpt-5.6-luna` with reasoning disabled, default temperature.

| | |
|---|---|
| False approvals | **4 / 50** |
| Correct terminal action | 44 / 50 |
| Cases with 5/5 agreement | 8 / 10 |
| Median cost per run | AUD 0.0008 |
| Total spend | AUD 0.04 |

False approvals are the headline. Over-escalating costs a human five minutes; over-approving costs
money. Every other number is context.

---

## The two findings worth your time

### A perfectly reproducible idempotency key that guaranteed nothing

Six independent runs of the same invoice, fresh context each time. Every one supplied the identical
key `INV-001-SUP-1001` — the planner derived it from two fields visible in the transcript rather
than generating anything.

So the premise was wrong. Non-determinism was never the problem.

The problem is that `approve_for_payment` writes the key into the payment record and **never reads
it**. No uniqueness check on the write path. A perfectly stable key against a tool that ignores keys
is worth exactly as much as a random one.

After an injected crash immediately following a successful approval, the restarted run did not
double-pay. But not because of the key — because the planner *chose* to call
`check_duplicate_payment` before deciding. That tool is optional, with no ordering constraint behind
it. Which brings us to the second finding.

### Identical evidence, divergent terminal action, on the only step with a side effect

Case 7: invoice, PO and goods receipt agree exactly. The vendor does not exist in master data, so
`get_vendor` returns an error.

All five attempts called the same five tools in the same order and received byte-identical results.
One escalated. **Four approved**, with the vendor error sitting in the transcript at the moment of
approval.

There is no path difference to blame — no missing lookup, no extra information, no step-count
variance. The divergence is confined to the terminal step.

An error returned from a tool carries no special weight. It is a string in the message list,
competing against a system prompt that says approve when invoice, PO and receipt agree — which they
did. The model has a defensible reading and takes the other one 20% of the time.

**A rule that is not stated is not enforced. And a rule that is stated is enforced unreliably:**
the tolerance thresholds were in the system prompt and still failed 2/5 on case 2.

---

## What that implies

- **Preconditions belong in the tool, not the prompt.** Compliance with prompt instructions ran
  between 60% and 100% depending on the rule. A tool that refuses to execute unless its
  preconditions are met is the only enforcement that does not degrade.
- **Terminal actions with side effects need a fourth outcome.** Approve, reject and escalate cannot
  express "already done". The restarted run reached `reject` — wrong, and operationally misleading,
  since an orchestrator would route a settled invoice to a dispute queue.
- **An eval harness over a side-effecting system needs explicit state reset, and its absence is
  silent.** One exploratory run wrote a payment that contaminated an entire fifty-run pass. The
  symptom was indistinguishable from model variance.
- **Measure agreement, not accuracy.** Case 7 at 1/5 correct would have looked like bad luck on a
  single run. The variance is the signal.

Full write-up, per-case table and five failure modes with trace references: **[FINDINGS.md](FINDINGS.md)**

---

## Method

```
messages = [system_prompt, user_prompt(case)]
for step in range(MAX_STEPS):        # 12, hard
    response = model.call(messages, tools=TOOL_SCHEMAS)
    if no tool call: break
    for call in response.tool_calls:
        result = dispatch(call)      # errors return as data, never raised
        messages.append(tool_result(call, result))
    if terminal tool called: break
```

Deliberate omissions, all of which would have hidden the measurement:

- No agent framework. The loop is ~130 lines and every step is visible.
- No retry logic, no self-correction prompt, no validation layer.
- Tool errors are returned to the model as `{"error": ...}` rather than raised, because what it does
  with an error is the thing being measured.
- Terminal actions are tool calls, never parsed from prose. A model that says "I'd approve this"
  without calling the tool is recorded as a failure, not an approval.
- MAX_STEPS is enforced. Hitting it is a finding, not a number to tune.

Nine tools over five flat JSON fixture files. `approve_for_payment` appends to
`payment_history.json` — the side-effect record and the subject of the experiment.

Every event appends one line to `traces/run_*.jsonl`, fsync'd, because the experiment kills a
process mid-run and buffered evidence is no evidence.

---

## Layout

```
fixtures/     five JSON files standing in for an ERP
tools.py      nine tools, their schemas, and dispatch
loop.py       the agent loop, model constants, system prompt
trace.py      JSONL writer, fixed schema
cases.py      ten cases and the expected terminal action for each
run.py        CLI: one case or all, N attempts
analyse.py    reads the traces, produces the per-case table
traces/       fifty runs, one file each
```

```bash
python run.py --all --repeat 5
python analyse.py
```

Needs `OPENAI_API_KEY` in `.env`.

---

## Scope

Two days. Not production, not a demo, not deployed anywhere. The code is crude on purpose — the
output is the failure inventory, and time spent making the loop elegant is time not spent counting
failures.

If you build agents over systems with real side effects, the interesting file is
[FINDINGS.md](FINDINGS.md).
