"""Tests for the CLI argument parser."""

from __future__ import annotations

from scorepilot.main import build_parser


def test_parser_defaults() -> None:
    args = build_parser("127.0.0.1", 8000).parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.no_browser is False
    assert args.reload is False


def test_parser_overrides() -> None:
    args = build_parser("127.0.0.1", 8000).parse_args(
        ["--host", "0.0.0.0", "--port", "9000", "--no-browser", "--reload"]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.no_browser is True
    assert args.reload is True
