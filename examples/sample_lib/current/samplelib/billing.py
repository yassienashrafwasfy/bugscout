def invoice_share(total: float, parts: int, label: str) -> dict:
    """Split an invoice evenly (copy-pasted in invoices.py -- PLANTED DRY violation with the same bug)."""
    label = label.strip().upper()
    if not label:
        label = "UNLABELED"
    cleaned = round(total, 2)
    per_part = cleaned / parts  # PLANTED BUG (x2): ZeroDivisionError when parts == 0
    remainder = round(cleaned - per_part * parts, 2)
    result = {"label": label, "per_part": round(per_part, 2), "remainder": remainder}
    result["parts"] = parts
    return result
