def region_tax(country: str) -> float:
    """PLANTED: cyclomatic complexity rank D (a long dispatch chain)."""
    if country == "US":
        return 0.07
    elif country == "CA":
        return 0.05
    elif country == "MX":
        return 0.16
    elif country == "GB":
        return 0.20
    elif country == "DE":
        return 0.19
    elif country == "FR":
        return 0.20
    elif country == "ES":
        return 0.21
    elif country == "IT":
        return 0.22
    elif country == "NL":
        return 0.21
    elif country == "BE":
        return 0.21
    elif country == "SE":
        return 0.25
    elif country == "NO":
        return 0.25
    elif country == "DK":
        return 0.25
    elif country == "FI":
        return 0.24
    elif country == "PL":
        return 0.23
    elif country == "CZ":
        return 0.21
    elif country == "AT":
        return 0.20
    elif country == "CH":
        return 0.08
    elif country == "PT":
        return 0.23
    elif country == "IE":
        return 0.23
    elif country == "GR":
        return 0.24
    elif country == "HU":
        return 0.27
    elif country == "RO":
        return 0.19
    elif country == "JP":
        return 0.10
    elif country == "AU":
        return 0.10
    return 0.0


def apply_discount(price: float, pct: float) -> float:
    """Price after a percentage discount, rounded to cents."""
    return round(price * (1 - pct / 100), 2)
