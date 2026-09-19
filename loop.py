import json
import time

from dotenv import load_dotenv
from openai import OpenAI

import tools
from trace import Trace

load_dotenv()
client = OpenAI()

MODEL_ID = "gpt-5.6-luna"
MAX_STEPS = 12

PRICE_IN = 0.20 / 1_000_000
PRICE_CACHED_IN = 0.02 / 1_000_000
PRICE_OUT = 1.20 / 1_000_000
USD_TO_AUD = 1.43
CRASH_AFTER_APPROVE = False

SYSTEM_PROMPT = (
    "You match supplier invoices against purchase orders and goods receipts. "
    "For each invoice, gather what you need using the tools, then take exactly "
    "one terminal action: approve_for_payment, reject, or escalate.\n"
    "Approve only when the invoice, PO and goods receipt all agree within tolerance.\n"
    "Tolerance: quantity within 2%, unit price within 1%, totals within AUD 50.\n"
    "Escalate anything you cannot resolve. Never guess a purchase order number."
)



def cost_aud(usage):
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0
    fresh = usage.prompt_tokens - cached
    usd = fresh * PRICE_IN + cached * PRICE_CACHED_IN + usage.completion_tokens * PRICE_OUT
    return round(usd * USD_TO_AUD, 8)


def run_case(case, attempt):
    tr = Trace(case["case_id"], attempt, MODEL_ID)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Process invoice {case['invoice_id']}."},
    ]
    terminal = None
    steps_used = 0

    for step in range(MAX_STEPS):
        steps_used = step + 1
        t0 = time.time()
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
            reasoning_effort="none",
        )
        latency = int((time.time() - t0) * 1000)
        choice = response.choices[0]
        usage = response.usage

        tr.model_call(step, usage.prompt_tokens, usage.completion_tokens,
                      cost_aud(usage), latency, choice.finish_reason)

        calls = choice.message.tool_calls
        if not calls:
            terminal = "NO_TERMINAL_TOOL"
            tr.terminal(step, None, "error",
                        choice.message.content)
            break

        messages.append(choice.message)

        for call in calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_unparseable": call.function.arguments}

            tr.tool_call(step, name, args)

            t1 = time.time()
            result, status = tools.dispatch(name, args)
            tool_latency = int((time.time() - t1) * 1000)

            if name in tools.TERMINAL_TOOLS and status == "ok":
                terminal = name
                tr.terminal(step, name, status, json.dumps(result))
            else:
                tr.tool_result(step, name, status, json.dumps(result), tool_latency)
            
            if (name == "approve_for_payment" and status == "ok"
                    and CRASH_AFTER_APPROVE):
                tr.close()
                raise RuntimeError("injected failure after side effect")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

        if terminal:
            break
    else:
        terminal = "MAX_STEPS_EXCEEDED"
        tr.terminal(MAX_STEPS - 1, None, "error", "max steps exceeded")

    tr.close()
    return {
        "run_id": tr.run_id,
        "case_id": case["case_id"],
        "attempt": attempt,
        "terminal": terminal,
        "expected": case["expected"],
        "correct": terminal == case["expected"],
        "steps": steps_used,
        "trace_path": tr.path,
    }