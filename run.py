import argparse
import json

import cases
from loop import run_case


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, help="run a single case id")
    ap.add_argument("--all", action="store_true", help="run all ten cases")
    ap.add_argument("--repeat", type=int, default=1, help="attempts per case")
    args = ap.parse_args()

    if args.all:
        selected = cases.CASES
    elif args.case:
        selected = [cases.BY_ID[args.case]]
    else:
        ap.error("pass --case N or --all")

    results = []
    for case in selected:
        for attempt in range(1, args.repeat + 1):
            r = run_case(case, attempt)
            mark = "ok " if r["correct"] else "MISS"
            print(f"{mark} case {r['case_id']:2} attempt {attempt} "
                  f"steps {r['steps']:2} -> {r['terminal']:20} "
                  f"(expected {r['expected']})")
            results.append(r)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    false_approve = sum(1 for r in results
                        if r["terminal"] == "approve_for_payment"
                        and r["expected"] != "approve_for_payment")
    print()
    print(f"correct        {correct}/{total}")
    print(f"false approves {false_approve}/{total}")

    with open("last_run.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()
import shutil

def reset_payments():
    shutil.copy("fixtures/payment_history.seed.json",
                "fixtures/payment_history.json")