import collections
import glob
import json
import os
import statistics

import cases

TRACE_DIR = "traces"
FIXTURES = "fixtures"


def valid_ids():
    def load(n):
        with open(os.path.join(FIXTURES, n), encoding="utf-8") as fh:
            return json.load(fh)
    ids = set()
    ids |= set(load("invoices.json").keys())
    ids |= set(load("purchase_orders.json").keys())
    ids |= set(load("goods_receipts.json").keys())
    ids |= set(load("vendors.json").keys())
    for inv in load("invoices.json").values():
        ids.add(inv.get("invoice_number"))
        ids.add(inv.get("vendor_id"))
    return {i for i in ids if i}


KNOWN = valid_ids()


def load_runs():
    runs = []
    for path in sorted(glob.glob(os.path.join(TRACE_DIR, "run_*.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            events = [json.loads(line) for line in fh if line.strip()]
        if not events:
            continue
        runs.append({"path": path, "events": events,
                     "case_id": events[0]["case_id"],
                     "attempt": events[0]["attempt"]})
    return runs


def summarise(run):
    events = run["events"]
    model_calls = [e for e in events if e["event"] == "model_call"]
    tool_calls = [e for e in events if e["event"] == "tool_call"]
    terminals = [e for e in events if e["event"] == "terminal"]

    terminal = terminals[-1]["tool"] if terminals else None
    if terminal is None and terminals:
        terminal = terminals[-1]["result_summary"]
    if not terminals:
        terminal = "NO_TERMINAL_EVENT"
    elif terminals[-1]["tool"] is None:
        terminal = "MAX_STEPS_OR_PROSE"

    seq = tuple(e["tool"] for e in tool_calls)

    hallucinated = 0
    for e in tool_calls:
        for k, v in (e["args"] or {}).items():
            if k == "idempotency_key":
                continue
            if isinstance(v, str) and v.startswith(("PO-", "INV-", "V-", "SUP-")):
                if v not in KNOWN:
                    hallucinated += 1

    failed = set()
    retries = 0
    by_step = collections.defaultdict(list)
    for e in events:
        if e["event"] in ("tool_call", "tool_result"):
            by_step[e["step"]].append(e)
    for e in tool_calls:
        sig = (e["tool"], json.dumps(e["args"], sort_keys=True))
        if sig in failed:
            retries += 1
        results = [r for r in events
                   if r["event"] == "tool_result" and r["step"] == e["step"]
                   and r["tool"] == e["tool"]]
        if results and results[-1]["result_status"] in ("error", "not_found"):
            failed.add(sig)

    return {
        "terminal": terminal,
        "steps": len(model_calls),
        "seq": seq,
        "cost": sum(e["cost_aud"] or 0 for e in model_calls),
        "latency": sum(e["latency_ms"] or 0 for e in model_calls),
        "hallucinated": hallucinated,
        "retries": retries,
        "path": run["path"],
        "attempt": run["attempt"],
    }


def main():
    runs = load_runs()
    by_case = collections.defaultdict(list)
    for r in runs:
        by_case[r["case_id"]].append(summarise(r))

    header = (f"{'#':>2} {'case':<24} {'expected':<20} {'agree':>6} {'corr':>5} "
              f"{'FA':>3} {'steps':>7} {'seqs':>5} {'cost':>9} {'hall':>5} {'retry':>6}")
    print(header)
    print("-" * len(header))

    tot_fa = tot_correct = tot_runs = 0
    all_costs, all_steps = [], []
    full_agree = 0

    for c in cases.CASES:
        rs = by_case.get(c["case_id"], [])
        if not rs:
            continue
        n = len(rs)
        terms = [r["terminal"] for r in rs]
        top, top_n = collections.Counter(terms).most_common(1)[0]
        correct = sum(1 for t in terms if t == c["expected"])
        fa = sum(1 for t in terms
                 if t == "approve_for_payment" and c["expected"] != "approve_for_payment")
        steps = [r["steps"] for r in rs]
        costs = [r["cost"] for r in rs]

        tot_fa += fa
        tot_correct += correct
        tot_runs += n
        all_costs += costs
        all_steps += steps
        if top_n == n:
            full_agree += 1

        print(f"{c['case_id']:>2} {c['name']:<24} {c['expected']:<20} "
              f"{top_n}/{n:<4} {correct}/{n:<3} {fa:>3} "
              f"{min(steps)}/{int(statistics.median(steps))}/{max(steps):<3} "
              f"{len(set(r['seq'] for r in rs)):>5} "
              f"{statistics.median(costs):>9.5f} "
              f"{sum(r['hallucinated'] for r in rs):>5} "
              f"{sum(r['retries'] for r in rs):>6}")

    print()
    print(f"false approvals          {tot_fa}/{tot_runs}")
    print(f"correct terminal action  {tot_correct}/{tot_runs}")
    print(f"cases with full agreement {full_agree}/{len(by_case)}")
    print(f"median cost per run      AUD {statistics.median(all_costs):.5f}")
    print(f"median steps per run     {statistics.median(all_steps)}")
    print(f"total spend              AUD {sum(all_costs):.4f}")

    print()
    print("split cases:")
    for c in cases.CASES:
        rs = by_case.get(c["case_id"], [])
        counts = collections.Counter(r["terminal"] for r in rs)
        if len(counts) > 1:
            print(f"  case {c['case_id']}: {dict(counts)}")
            for r in sorted(rs, key=lambda x: x["attempt"]):
                print(f"    a{r['attempt']} {r['terminal']:<20} {r['path']}")


if __name__ == "__main__":
    main()