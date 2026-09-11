"""mitmproxy addon: dump full request/response for bosch-related hosts to a text file.

Usage: mitmdump -s mitm_dump_bosch.py

Output goes to $BOSCH_MITM_OUT (default: bosch_flows.txt in the working
directory). Credentials are redacted by default -- Authorization/Cookie
headers, and the bodies of SingleKey ID (login/token) flows, which carry
authorization codes and refresh tokens. Set BOSCH_MITM_RAW=1 to disable
redaction when debugging the login flow itself; treat that file like a
password afterwards.
"""
import os

from mitmproxy import http

OUT = os.environ.get("BOSCH_MITM_OUT", "bosch_flows.txt")
RAW = os.environ.get("BOSCH_MITM_RAW") == "1"

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


def _header_value(name: str, value: str) -> str:
    if not RAW and name.lower() in SENSITIVE_HEADERS:
        return "(redacted)"
    return value


def _body(message, host: str) -> str:
    if not RAW and "singlekey" in host:
        return "(redacted)"
    try:
        return message.get_text(strict=False) or ""
    except Exception as e:
        return f"(body error: {e})"


def response(flow: http.HTTPFlow) -> None:
    host = flow.request.pretty_host.lower()
    if "bosch" not in host and "singlekey" not in host:
        return
    with open(OUT, "a", encoding="utf-8") as f:
        f.write("\n==== FLOW ====\n")
        f.write(f"{flow.request.method} {flow.request.pretty_url}\n")
        f.write("--- Request headers ---\n")
        for k, v in flow.request.headers.items():
            f.write(f"{k}: {_header_value(k, v)}\n")
        f.write("--- Request body ---\n")
        f.write(_body(flow.request, host) + "\n")
        f.write("--- Response headers ---\n")
        for k, v in flow.response.headers.items():
            f.write(f"{k}: {_header_value(k, v)}\n")
        f.write("--- Response body ---\n")
        f.write(_body(flow.response, host) + "\n")
