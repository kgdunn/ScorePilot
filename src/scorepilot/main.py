"""Command-line entry point.

``scorepilot`` boots uvicorn in a single process and (optionally) opens a browser.
No Node is involved at runtime; the built frontend is served as static files.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from scorepilot.config import get_settings


def build_parser(defaults_host: str, defaults_port: int) -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="scorepilot",
        description="Launch the ScorePilot server and open the browser.",
    )
    parser.add_argument("--host", default=defaults_host, help="Host to bind.")
    parser.add_argument("--port", type=int, default=defaults_port, help="Port to bind.")
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser on startup."
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development).")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and run the uvicorn server."""
    settings = get_settings()
    args = build_parser(settings.host, settings.port).parse_args(argv)

    if settings.open_browser and not args.no_browser and not args.reload:
        url = f"http://{args.host}:{args.port}"
        # Open the browser shortly after the server starts accepting connections.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "scorepilot.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
