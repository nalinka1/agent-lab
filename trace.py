import json
import os
import uuid
from datetime import datetime, timezone

TRACE_DIR = "traces"

FIELDS = [
    "run_id", "case_id", "attempt", "step", "ts", "event", "model_id",
    "tool", "args", "result_status", "result_summary",
    "tokens_in", "tokens_out", "cost_aud", "latency_ms", "stop_reason",
]


def new_run_id():
    return uuid.uuid4().hex[:8]


def truncate(value, limit=200):
    if value is None:
        return None
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    return s if len(s) <= limit else s[:limit] + "..."


class Trace:
    def __init__(self, case_id, attempt, model_id, run_id=None):
        os.makedirs(TRACE_DIR, exist_ok=True)
        self.run_id = run_id or new_run_id()
        self.case_id = case_id
        self.attempt = attempt
        self.model_id = model_id
        name = f"run_c{case_id:02d}_a{attempt}_{self.run_id}.jsonl"
        self.path = os.path.join(TRACE_DIR, name)
        self.fh = open(self.path, "a", encoding="utf-8")

    def _write(self, **kwargs):
        row = {f: None for f in FIELDS}
        row["run_id"] = self.run_id
        row["case_id"] = self.case_id
        row["attempt"] = self.attempt
        row["model_id"] = self.model_id
        row["ts"] = datetime.now(timezone.utc).isoformat()
        row.update({k: v for k, v in kwargs.items() if k in FIELDS})
        self.fh.write(json.dumps(row, default=str) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def model_call(self, step, tokens_in, tokens_out, cost_aud,
                   latency_ms, stop_reason):
        self._write(step=step, event="model_call", tokens_in=tokens_in,
                    tokens_out=tokens_out, cost_aud=cost_aud,
                    latency_ms=latency_ms, stop_reason=stop_reason)

    def tool_call(self, step, tool, args):
        self._write(step=step, event="tool_call", tool=tool, args=args)

    def tool_result(self, step, tool, result_status, result_summary,
                    latency_ms=None):
        self._write(step=step, event="tool_result", tool=tool,
                    result_status=result_status,
                    result_summary=truncate(result_summary),
                    latency_ms=latency_ms)

    def terminal(self, step, tool, result_status, result_summary=None):
        self._write(step=step, event="terminal", tool=tool,
                    result_status=result_status,
                    result_summary=truncate(result_summary))

    def close(self):
        self.fh.close()