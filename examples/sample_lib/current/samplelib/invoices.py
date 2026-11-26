def invoice_share_copy(total: float, parts: int, label: str) -> dict:
    """Copy of billing.invoice_share (PLANTED DRY violation with the same bug)."""
    label = label.strip().upper()
    if not label:
        label = "UNLABELED"
    cleaned = round(total, 2)
    per_part = cleaned / parts  # same bug, copy-pasted
    remainder = round(cleaned - per_part * parts, 2)
    result = {"label": label, "per_part": round(per_part, 2), "remainder": remainder}
    result["parts"] = parts
    return result
