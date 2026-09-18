# Agent Failure Lab — Brief

**One line:** Build a raw tool-calling agent over three-way invoice matching, run it fifty times,
and write down every way it breaks.

---

## 1. Why this exists

Three gaps, one weekend.

1. **Feel for agentic failure modes.** The concept is a loop — model picks a tool, tool runs, result
   returns to context, repeat until stop. That is ten minutes of reading. What is not obvious from
   reading is how it fails, because the planner is non-deterministic and backend instincts do not
   transfer cleanly.
2. **Python as something other than a scripting sideline.**
3. **Something specific to say in a conversation.** Not a CV line. A first conversation with an
   automation company goes differently if you can describe real traces instead of expressing
   interest.

## 2. What this is not

- **Not a portfolio project.** Agent demos are saturated. Nobody is impressed by one.
- **Not production anything.** No deployment, no infrastructure, no UI.
- **Not connected to the Sovereign AI Boundary project.** Different repo, different conversation,
  no shared code. If the two converge later, that is a decision to make later with evidence.

## 3. The task: three-way invoice matching

Invoice, purchase order, goods receipt. Do they agree? Approve, reject, or escalate.

Chosen over **claims triage** because the correctness criteria are crisp — you can grade every case
objectively — and because approval has a real side effect, which is where the interesting failures
live. Claims triage is fuzzier to grade, which would waste Sunday arguing about whether output was
right.

Chosen over **a generic toy task** (research assistant, email summariser) because you already know
this domain cold. Wrong output is obvious to you in one second. That is the whole point: you are
grading the agent, and you can only grade what you already understand.

## 4. Success criteria

Success is **not** "the agent gets ten out of ten." Success is a populated FINDINGS.md.

| Done means | |
|---|---|
| The loop runs all ten cases end to end | Saturday |
| Fifty traces exist on disk, five runs per case | Sunday morning |
| Decision agreement rate computed per case | Sunday |
| At least five distinct failure modes documented with trace references | Sunday |
| The side-effect experiment run and its result recorded | Sunday |

If the agent handles every case perfectly five times out of five, the fixtures were too easy.
Make case 10 harder and rerun.

## 5. Shape of the two days

**Saturday — make it run.**
Fixtures, tools, loop, one full pass over ten cases. Crude is fine. Print statements are fine.
The only thing that must be right is the trace writer, because Sunday depends on it.

**Sunday — break it and count.**
Five runs per case. Diff the traces. Compute the numbers. Run the side-effect experiment. Write
FINDINGS.md.

Sunday is the project. Saturday is setup for Sunday. If Saturday overruns, cut tools down to the
minimum five in SPEC.md rather than borrowing Sunday.

## 6. Non-goals, explicitly

| Excluded | Why |
|---|---|
| Agent framework in the first pass | You would learn the framework's abstractions and never see the loop. Optional two-hour port afterwards, to find out what it bought you |
| n8n / Make / low-code | Commercially informative — a lot of automation shops run on it — but teaches nothing as an engineer |
| Memory, RAG, vector store | Unrelated to the failure modes this targets |
| Multi-agent | Adds coordination failure on top of planner failure. You cannot attribute anything |
| Retry and recovery logic | Sunday is about observing failure, not fixing it. Fixes are a later project if the findings justify one |
| Any cloud deployment | Nothing here needs it |

## 7. The thing to watch for

Your background makes you unusually likely to spot this, and it is the most valuable output of the
weekend: **what happens when a tool has a side effect and the run fails halfway through.**

The agent approves an invoice for payment, then the next step errors, then the run restarts. Does it
approve again? Under a non-deterministic planner, an idempotency key only helps if the planner
reconstructs the same key — and there is no guarantee it will. Compensating actions assume a plan
you can walk backwards, and there is no plan, only a history.

This is standard ground in payments and largely unexplored by people currently building agents. If
one thing from this weekend is worth writing up publicly, it is this.

## 8. Optional epilogue

Two hours, only if the weekend went fast: port the same loop to a current agent framework and record
what it gave you and what it hid. Verify the framework landscape before picking one — it moves as
fast as the model list.
