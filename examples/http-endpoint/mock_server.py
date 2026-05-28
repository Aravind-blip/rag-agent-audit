"""Small local HTTP server for the rag-agent-audit HTTP example.

This is not a real RAG app. It mimics the response shape a production RAG
or agent endpoint might return: answer, citations, retrieved sources, and
agent tool calls.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        raw_body = self.rfile.read(length)

        try:
            body: dict[str, Any] = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        question = str(body.get("question", "")).lower()

        if "refund" in question:
            response = {
                "answer": "Refunds are available within 30 days for eligible purchases.",
                "citations": [{"source": "org_a_refund_policy.pdf"}],
                "debug": {"retrieved": [{"source": "org_a_refund_policy.pdf"}]},
                "tool_calls": [],
            }
        elif "organization b" in question:
            response = {
                "answer": "I could not find that information in the available sources.",
                "citations": [],
                "debug": {"retrieved": []},
                "tool_calls": [],
            }
        elif "delete" in question:
            response = {
                "answer": (
                    "I could not find support for performing that action "
                    "in the available sources."
                ),
                "citations": [],
                "debug": {"retrieved": []},
                "tool_calls": [],
            }
        else:
            response = {
                "answer": "I could not find that information in the available sources.",
                "citations": [],
                "debug": {"retrieved": []},
                "tool_calls": [],
            }

        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
