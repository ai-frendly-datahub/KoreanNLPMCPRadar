#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any


TOOLS = [
    {
        "name": "dictionary_status",
        "title": "Dictionary Status",
        "description": "Return local dictionary cache and import status.",
        "inputSchema": {"type": "object", "properties": {}},
    }
]

STATUS_PAYLOAD = {
    "ready": True,
    "data_dir": "fixture://ko-stdict",
    "db_path": "fixture://ko-stdict/stdict.sqlite",
    "source_filename": "fixture-stdict.json",
    "source_date": "2026-04-29",
    "entry_count": 2,
    "imported_at": "2026-04-29T00:00:00+00:00",
    "schema_version": 2,
}


def write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def response_for(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-ko-stdict-mcp", "version": "0.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if params.get("name") != "dictionary_status":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "Unsupported tool"}],
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps(STATUS_PAYLOAD, ensure_ascii=False)}
                ],
                "structuredContent": STATUS_PAYLOAD,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unsupported method: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = response_for(message)
        if response is not None:
            write_message(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
