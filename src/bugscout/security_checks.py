"""Pure logic for the security probes: payload corpus, response analysis, repro expectations. No I/O, so it is unit-testable.

The corpus is fixed and versioned in this file on purpose: probes must be reproducible and bounded, and an LLM host cannot widen
them by inventing payloads. Detectors are conservative: each one needs positive evidence in the response, not just an odd status.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

CORPUS_VERSION = "1"
MARK = "bscout7f3a"
CALC = "1337*7"          # shell payloads compute this; 9359 can only appear if the payload was executed
CALC_RESULT = "9359"
EVIL_ORIGIN = "https://evil.example"

CLASSES = {  # class -> (CWE, title fragment, default severity)
    "sqli": ("CWE-89", "SQL injection", "high"),
    "path_traversal": ("CWE-22", "path traversal", "high"),
    "cmd_injection": ("CWE-78", "OS command injection", "critical"),
    "xss": ("CWE-79", "reflected cross-site scripting", "medium"),
    "info_leak": ("CWE-209", "stack trace leaked to the client", "low"),
    "missing_auth": ("CWE-306", "endpoint declared as protected answers without credentials", "high"),
    "bola": ("CWE-639", "broken object-level authorization (IDOR)", "high"),
    "cors": ("CWE-942", "permissive CORS policy", "medium"),
    "headers": ("CWE-693", "missing security headers", "low"),
}

SQL_ERRORS = ("sqlite3.", "operationalerror", "sql syntax", "syntax error at or near", "unterminated quoted string",
              "unclosed quotation mark", "sqlstate", "psycopg", "ora-0", "mysql_fetch", "pg_query")
TRACE_MARKERS = ("traceback (most recent call last)", "stack trace:", "at java.")
SECURITY_HEADERS = ("x-content-type-options", "x-frame-options", "content-security-policy")

SQLI = {"sqli_quote": "'", "sqli_true": "' OR '1'='1", "sqli_false": "' AND '1'='2"}
TRAVERSAL = {"traversal_0": "../../../../../../etc/passwd", "traversal_1": "....//....//....//....//etc/passwd"}
CMD = {"cmd_0": f";echo $(({CALC}))", "cmd_1": f"$(echo $(({CALC})))", "cmd_2": f"|echo $(({CALC}))"}
XSS = {"xss": f"<{MARK}>"}
PAYLOADS: dict[str, str] = {**SQLI, **TRAVERSAL, **CMD, **XSS}
PASSWD = r"root:[^:\n]*:0:0:"


def text_of(resp: dict | None) -> str:
    return (resp or {}).get("text") or ""


def status_of(resp: dict | None) -> int:
    return int((resp or {}).get("status_code") or 0)


def is_2xx(resp: dict | None) -> bool:
    return 200 <= status_of(resp) < 300


def lower_headers(resp: dict | None) -> dict[str, str]:
    return {k.lower(): str(v) for k, v in ((resp or {}).get("headers") or {}).items()}


def sample_value(schema: dict | None) -> Any:
    """A harmless valid value for a parameter that is not being attacked."""
    s = schema or {}
    if s.get("enum"):
        return s["enum"][0]
    return {"integer": 1, "number": 1.0, "boolean": True}.get(s.get("type"), "test")


def attackable(param: dict) -> bool:
    """Only free-text parameters are worth injecting into; integers and enums are rejected by validation."""
    s = param.get("schema") or {}
    return param.get("in") in ("query", "path") and s.get("type", "string") == "string" and not s.get("enum")


def fill_path(template: str, values: dict[str, Any]) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", quote(str(v), safe=""))
    return out


# ---------------------------------------------------------------- injection analysis
def analyse_injection(responses: dict[str, dict]) -> list[dict]:
    """responses: probe name -> response, needs 'control'. Returns [{class, probe, evidence, expect}], one per class at most."""
    ctl = responses.get("control") or {}
    ctl_text = text_of(ctl).lower()
    out: list[dict] = []

    # SQL injection: a database error that the harmless control does not show, else a boolean-based difference
    q = responses.get("sqli_quote")
    if q:
        qt = text_of(q).lower()
        sig = next((s for s in SQL_ERRORS if s in qt and s not in ctl_text), None)
        if sig:
            out.append({"class": "sqli", "probe": "sqli_quote", "evidence": f"database error text ('{sig}') after a single quote",
                        "expect": {"body_contains": sig}})
    t, f = responses.get("sqli_true"), responses.get("sqli_false")
    if not out and t and f and is_2xx(t) and is_2xx(f) and is_2xx(ctl) and text_of(f) == text_of(ctl) and len(text_of(t)) > len(text_of(f)):
        out.append({"class": "sqli", "probe": "sqli_true",
                    "evidence": f"' OR '1'='1 returned {len(text_of(t))} bytes; the always-false variant and the control {len(text_of(f))}",
                    "expect": {"status_in": [200], "min_body_len": len(text_of(f)) + 1}})

    # path traversal: the content of /etc/passwd comes back
    for name in TRAVERSAL:
        r = responses.get(name)
        if r and re.search(PASSWD, text_of(r)) and not re.search(PASSWD, ctl_text):
            out.append({"class": "path_traversal", "probe": name, "evidence": "the response contains /etc/passwd",
                        "expect": {"body_regex": PASSWD}})
            break

    # command injection: an arithmetic result that only a shell could have produced
    for name in CMD:
        r = responses.get(name)
        if r and CALC_RESULT in text_of(r) and CALC_RESULT not in ctl_text:
            out.append({"class": "cmd_injection", "probe": name, "evidence": f"the server computed {CALC} = {CALC_RESULT}",
                        "expect": {"body_contains": CALC_RESULT}})
            break

    # reflected XSS: the raw tag comes back in an HTML response
    x = responses.get("xss")
    if x and f"<{MARK}>" in text_of(x) and "html" in lower_headers(x).get("content-type", "").lower():
        out.append({"class": "xss", "probe": "xss", "evidence": "the raw tag is reflected in a text/html response",
                    "expect": {"body_contains": f"<{MARK}>", "header_contains": {"content-type": "html"}}})

    # information leak: a probe made the server print a stack trace that the control did not
    for name, r in responses.items():
        hit = [m for m in TRACE_MARKERS if m in text_of(r).lower()]
        if name != "control" and hit and not any(m in ctl_text for m in TRACE_MARKERS):
            out.append({"class": "info_leak", "probe": name, "evidence": "a stack trace is returned to the client",
                        "expect": {"body_contains_any": hit}})
            break
    return out


# ---------------------------------------------------------------- hardening analysis
def analyse_headers(resp: dict) -> dict | None:
    """JSON-only APIs only need nosniff; HTML responses also need framing protection (X-Frame-Options or CSP)."""
    h = lower_headers(resp)
    missing = []
    if "x-content-type-options" not in h:
        missing.append("x-content-type-options")
    if "html" in h.get("content-type", "") and "x-frame-options" not in h and "content-security-policy" not in h:
        missing += ["x-frame-options", "content-security-policy"]
    if not missing:
        return None
    return {"class": "headers", "evidence": f"missing {', '.join(missing)}", "expect": {"header_absent": [missing[0]]}}


def analyse_cors(resp: dict) -> dict | None:
    h = lower_headers(resp)
    acao, acac = h.get("access-control-allow-origin"), h.get("access-control-allow-credentials", "").lower()
    if acao == EVIL_ORIGIN or (acao == "*" and acac == "true"):
        return {"class": "cors", "evidence": f"Access-Control-Allow-Origin: {acao} (credentials: {acac or 'not set'}) for an unknown origin",
                "expect": {"header_equals_any": {"access-control-allow-origin": [EVIL_ORIGIN, "*"]}}}
    return None


# ---------------------------------------------------------------- replay of a recorded security repro
def eval_expect(resp: dict, expect: dict) -> tuple[bool, dict]:
    """True when the response still shows the recorded evidence. Every given condition must hold."""
    text = text_of(resp)
    h = lower_headers(resp)
    checks: dict[str, bool] = {}
    if "status_in" in expect:
        checks["status_in"] = status_of(resp) in expect["status_in"]
    if "status_2xx" in expect:
        checks["status_2xx"] = is_2xx(resp)
    if "body_contains" in expect:
        checks["body_contains"] = expect["body_contains"].lower() in text.lower()
    if "body_contains_any" in expect:
        checks["body_contains_any"] = any(m.lower() in text.lower() for m in expect["body_contains_any"])
    if "body_regex" in expect:
        checks["body_regex"] = bool(re.search(expect["body_regex"], text))
    if "min_body_len" in expect:
        checks["min_body_len"] = len(text) >= expect["min_body_len"]
    if "header_contains" in expect:
        checks["header_contains"] = all(v.lower() in h.get(k.lower(), "").lower() for k, v in expect["header_contains"].items())
    if "header_absent" in expect:
        checks["header_absent"] = all(k.lower() not in h for k in expect["header_absent"])
    if "header_equals_any" in expect:
        checks["header_equals_any"] = all(h.get(k.lower()) in v for k, v in expect["header_equals_any"].items())
    return bool(checks) and all(checks.values()), {"status_code": status_of(resp), "checks": checks}


# ---------------------------------------------------------------- secrets
SECRET_PATTERNS = [  # (name, regex, severity)
    ("private key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----", "critical"),
    ("AWS access key id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "high"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", "high"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b", "high"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b", "high"),
    ("JWT", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "medium"),
    ("credentials in URL", r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]{3,}@[^/\s]+", "medium"),
    ("hardcoded secret", r"""(?i)\b[\w.]*(?:password|passwd|secret|api[_-]?key|token|private[_-]?key)[\w.]*\s*[:=]\s*(['"])[^'"\s]{8,}\1""", "medium"),
]
PLACEHOLDER = re.compile(r"(?i)^(?:x+|\*+|changeme|change[_-]?me|example.*|your[_-].*|<.*>|\$\{.*\}|%\(.*\)s|none|null|test.*|dummy|placeholder.*)$")


def looks_like_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.match(value)) or len(set(value)) <= 2


def redact(line: str) -> str:
    return re.sub(r"""(['"])([^'"\s]{3})[^'"\s]{4,}\1""", r"\1\2…\1", line)[:160]


def scan_text(text: str) -> list[dict]:
    """[{line, name, severity, snippet}] with values redacted."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if len(line) > 600:
            continue
        for name, rx, sev in SECRET_PATTERNS:
            m = re.search(rx, line)
            if not m:
                continue
            if name == "hardcoded secret":
                val = re.search(r"""(['"])([^'"\s]{8,})\1""", line[m.start():])
                if val and looks_like_placeholder(val.group(2)):
                    continue
            out.append({"line": n, "name": name, "severity": sev, "snippet": redact(line.strip())})
            break
    return out
