from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from radar.collector import _collect_single, collect_sources
from radar.exceptions import NetworkError, SourceError
from radar.mcp_source import _jsonrpc_result, collect_mcp_server_source
from radar.models import Source


HANGING_MCP_SERVER = "import time; time.sleep(30)"


def test_mcp_server_source_invokes_allowlisted_tool(monkeypatch) -> None:
    source = Source(
        name="Example MCP",
        type="mcp_server",
        url="mcp://example",
        config={
            "transport": "stdio",
            "command": "example-mcp",
            "tools": [{"name": "search", "arguments": {"query": "radar"}}],
            "timeout_seconds": 3,
            "max_items": 5,
        },
    )
    observed = {}

    def fake_payloads(_source, config):
        observed["transport"] = config.transport
        observed["tool"] = config.tools[0].name
        observed["arguments"] = config.tools[0].arguments
        return [
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"title": "Example MCP result", '
                            '"url": "https://example.com/result", '
                            '"summary": "normalized from MCP tool"}'
                        ),
                    }
                ]
            }
        ]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert observed == {
        "transport": "stdio",
        "tool": "search",
        "arguments": {"query": "radar"},
    }
    assert len(articles) == 1
    assert articles[0].title == "Example MCP result"
    assert articles[0].link == "https://example.com/result"
    assert articles[0].summary == "normalized from MCP tool"
    assert articles[0].source == "Example MCP"
    assert articles[0].category == "mcp"


def test_disabled_mcp_server_source_is_not_executed(monkeypatch) -> None:
    source = Source(
        name="Disabled MCP",
        type="mcp_server",
        url="mcp://disabled",
        enabled=False,
        config={"transport": "stdio", "command": "should-not-run", "tools": ["search"]},
    )

    def fail_if_called(_source, _config):
        raise AssertionError("disabled MCP source should not be invoked")

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fail_if_called)

    articles, errors = collect_sources(
        [source],
        category="mcp",
        min_interval_per_host=0.0,
        max_workers=1,
    )

    assert articles == []
    assert errors == []


def test_required_env_missing_fails_before_process_launch(monkeypatch) -> None:
    monkeypatch.delenv("MCP_RADAR_TEST_API_KEY", raising=False)
    source = Source(
        name="Env-gated MCP",
        type="mcp_server",
        url="mcp://env-gated",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", "raise SystemExit(99)"],
            "tools": ["search"],
            "env": ["MCP_RADAR_TEST_API_KEY"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(SourceError, match="Missing required MCP env var"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_mcp_payload_without_url_uses_safe_fallback(monkeypatch) -> None:
    source = Source(
        name="Fallback MCP",
        type="mcp_stdio",
        url="",
        id="fallback-mcp",
        config={"command": "example-mcp", "tools": ["list_items"], "max_items": 1},
    )

    def fake_payloads(_source, _config):
        return [{"content": [{"type": "text", "text": "plain text result"}]}]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert len(articles) == 1
    assert articles[0].title == "plain text result"
    assert articles[0].link == "mcp://fallback-mcp#plain%20text%20result"


def test_stdio_runtime_timeout_reports_request_context() -> None:
    source = Source(
        name="Hanging MCP",
        type="mcp_server",
        url="mcp://hanging",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", HANGING_MCP_SERVER],
            "tools": ["search"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(NetworkError, match="response 1 after 1s"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_mcp_tool_result_error_payload_is_rejected() -> None:
    message = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": "dictionary cache initialization failed"},
                        ensure_ascii=False,
                    ),
                }
            ]
        },
    }

    with pytest.raises(RuntimeError, match="MCP tool result error"):
        _jsonrpc_result(message)


def test_ko_stdict_fake_stdio_fixture_collects_dictionary_status() -> None:
    fixture = Path("fixtures/mcp/fake_ko_stdict_mcp.py")
    source = Source(
        name="dahlia/ko-stdict-mcp",
        type="mcp_server",
        url="https://github.com/dahlia/ko-stdict-mcp",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(fixture)],
            "tools": [{"name": "dictionary_status", "arguments": {}}],
            "timeout_seconds": 5,
            "max_items": 5,
        },
    )

    articles = collect_mcp_server_source(source, category="korean_nlp_mcp", limit=5, timeout=5)

    assert len(articles) == 1
    assert articles[0].title == "dahlia/ko-stdict-mcp"
    assert articles[0].link == "https://github.com/dahlia/ko-stdict-mcp#dahlia%2Fko-stdict-mcp"
    assert '"entry_count": 2' in articles[0].summary
    assert articles[0].category == "korean_nlp_mcp"
