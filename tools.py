import json
import os
import uuid

FIXTURES = "fixtures"
PAYMENTS = os.path.join(FIXTURES, "payment_history.json")


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


def get_invoice(invoice_id):
    inv = _load("invoices.json").get(invoice_id)
    return inv if inv else {"error": "not_found", "invoice_id": invoice_id}


def get_purchase_order(po_number):
    po = _load("purchase_orders.json").get(po_number)
    return po if po else {"error": "not_found", "po_number": po_number}


def get_goods_receipt(po_number):
    gr = _load("goods_receipts.json").get(po_number)
    return gr if gr else {"error": "not_found", "po_number": po_number}


def get_vendor(vendor_id):
    v = _load("vendors.json").get(vendor_id)
    return v if v else {"error": "vendor_not_in_master_data", "vendor_id": vendor_id}


def find_purchase_orders(vendor_id, amount_aud=None):
    out = []
    for po in _load("purchase_orders.json").values():
        if po["vendor_id"] != vendor_id or po["status"] != "open":
            continue
        if amount_aud is not None and abs(po["total"] - amount_aud) > 0.01:
            continue
        out.append(po)
    return {"matches": out, "count": len(out)}


def check_duplicate_payment(vendor_id, invoice_number):
    for p in json.load(open(PAYMENTS, encoding="utf-8")):
        if p["vendor_id"] == vendor_id and p["invoice_number"] == invoice_number:
            return {"already_paid": True, "payment_ref": p["payment_ref"],
                    "paid_date": p["paid_date"]}
    return {"already_paid": False, "payment_ref": None}


def approve_for_payment(invoice_id, amount_aud, idempotency_key):
    inv = _load("invoices.json").get(invoice_id)
    if not inv:
        return {"error": "not_found", "invoice_id": invoice_id}
    history = json.load(open(PAYMENTS, encoding="utf-8"))
    ref = "PAY-" + uuid.uuid4().hex[:6].upper()
    history.append({
        "payment_ref": ref,
        "vendor_id": inv["vendor_id"],
        "invoice_number": inv["invoice_number"],
        "amount_aud": amount_aud,
        "idempotency_key": idempotency_key,
        "paid_date": "2026-09-19",
    })
    with open(PAYMENTS, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)
    return {"payment_ref": ref, "status": "approved"}


def reject(invoice_id, reason):
    return {"status": "rejected", "invoice_id": invoice_id, "reason": reason}


def escalate(invoice_id, reason):
    return {"ticket": "TKT-" + uuid.uuid4().hex[:6].upper(),
            "invoice_id": invoice_id, "reason": reason}


TERMINAL_TOOLS = {"approve_for_payment", "reject", "escalate"}

REGISTRY = {
    "get_invoice": get_invoice,
    "get_purchase_order": get_purchase_order,
    "get_goods_receipt": get_goods_receipt,
    "get_vendor": get_vendor,
    "find_purchase_orders": find_purchase_orders,
    "check_duplicate_payment": check_duplicate_payment,
    "approve_for_payment": approve_for_payment,
    "reject": reject,
    "escalate": escalate,
}


def _schema(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props,
                       "required": required, "additionalProperties": False}}}


S = {"type": "string"}
N = {"type": "number"}

TOOL_SCHEMAS = [
    _schema("get_invoice", "Fetch an invoice by its id.",
            {"invoice_id": S}, ["invoice_id"]),
    _schema("get_purchase_order", "Fetch a purchase order by its number.",
            {"po_number": S}, ["po_number"]),
    _schema("get_goods_receipt", "Fetch the goods receipt for a purchase order number.",
            {"po_number": S}, ["po_number"]),
    _schema("get_vendor", "Fetch vendor master data by vendor id.",
            {"vendor_id": S}, ["vendor_id"]),
    _schema("find_purchase_orders",
            "List open purchase orders for a vendor, optionally filtered by total amount.",
            {"vendor_id": S, "amount_aud": N}, ["vendor_id"]),
    _schema("check_duplicate_payment",
            "Check whether this vendor and invoice number were already paid.",
            {"vendor_id": S, "invoice_number": S}, ["vendor_id", "invoice_number"]),
    _schema("approve_for_payment",
            "Terminal action. Approve the invoice and record a payment.",
            {"invoice_id": S, "amount_aud": N, "idempotency_key": S},
            ["invoice_id", "amount_aud", "idempotency_key"]),
    _schema("reject", "Terminal action. Reject the invoice.",
            {"invoice_id": S, "reason": S}, ["invoice_id", "reason"]),
    _schema("escalate", "Terminal action. Send the invoice to a human.",
            {"invoice_id": S, "reason": S}, ["invoice_id", "reason"]),
]


def dispatch(name, args):
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": "unknown_tool", "tool": name}, "error"
    try:
        result = fn(**args)
    except TypeError as e:
        return {"error": "bad_arguments", "detail": str(e)}, "error"
    except Exception as e:
        return {"error": "tool_failed", "detail": str(e)}, "error"
    if isinstance(result, dict) and "error" in result:
        status = "not_found" if result["error"] == "not_found" else "error"
        return result, status
    return result, "ok"