CASES = [
    {"case_id": 1,  "invoice_id": "INV-001", "expected": "approve_for_payment",
     "name": "exact match"},
    {"case_id": 2,  "invoice_id": "INV-002", "expected": "approve_for_payment",
     "name": "qty within tolerance"},
    {"case_id": 3,  "invoice_id": "INV-003", "expected": "escalate",
     "name": "price over tolerance"},
    {"case_id": 4,  "invoice_id": "INV-004", "expected": "escalate",
     "name": "no goods receipt"},
    {"case_id": 5,  "invoice_id": "INV-005", "expected": "reject",
     "name": "duplicate invoice"},
    {"case_id": 6,  "invoice_id": "INV-006", "expected": "escalate",
     "name": "partial delivery"},
    {"case_id": 7,  "invoice_id": "INV-007", "expected": "escalate",
     "name": "vendor lookup error"},
    {"case_id": 8,  "invoice_id": "INV-008", "expected": "escalate",
     "name": "currency mismatch"},
    {"case_id": 9,  "invoice_id": "INV-009", "expected": "escalate",
     "name": "missing PO number"},
    {"case_id": 10, "invoice_id": "INV-010", "expected": "escalate",
     "name": "ambiguous PO"},
]

BY_ID = {c["case_id"]: c for c in CASES}