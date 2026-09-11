"""mitmproxy addon: dump full request/response for bosch-related hosts to a text file."""
from mitmproxy import http

OUT = r"C:\bosch-debug\bosch_flows.txt"


def response(flow: http.HTTPFlow) -> None:
    host = flow.request.pretty_host.lower()
    if "bosch" not in host and "singlekey" not in host:
        return
    with open(OUT, "a", encoding="utf-8") as f:
        f.write("\n==== FLOW ====\n")
        f.write(f"{flow.request.method} {flow.request.pretty_url}\n")
        f.write("--- Request headers ---\n")
        for k, v in flow.request.headers.items():
            f.write(f"{k}: {v}\n")
        f.write("--- Request body ---\n")
        try:
            f.write((flow.request.get_text(strict=False) or "") + "\n")
        except Exception as e:
            f.write(f"(request body error: {e})\n")
        f.write("--- Response headers ---\n")
        for k, v in flow.response.headers.items():
            f.write(f"{k}: {v}\n")
        f.write("--- Response body ---\n")
        try:
            f.write((flow.response.get_text(strict=False) or "") + "\n")
        except Exception as e:
            f.write(f"(response body error: {e})\n")
