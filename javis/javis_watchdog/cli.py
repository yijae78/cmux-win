"""Watchdog CLI: python -m javis.watchdog start|status|stop"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import WatchdogConfig
from .orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments. None uses sys.argv.

    Returns:
        Exit code (0 = success).
    """
    parser = argparse.ArgumentParser(
        prog="javis.watchdog",
        description="Javis Fleet Auto-Recovery Watchdog",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    start_p = sub.add_parser("start", help="Start watchdog")
    start_p.add_argument(
        "--config", type=Path, default=None,
        help="Path to JSON config file",
    )
    start_p.add_argument(
        "--audit-dir", type=Path,
        default=Path("javis/watchdog/audit"),
        help="Directory for JSONL audit logs",
    )

    # status
    sub.add_parser("status", help="Show fleet status")

    # stop
    sub.add_parser("stop", help="Stop running watchdog")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "start":
        config = _load_config(args.config)
        orch = Orchestrator(
            config=config, audit_dir=args.audit_dir,
        )
        orch.start()
        return 0

    if args.command == "status":
        orch = Orchestrator(config=WatchdogConfig())
        status = orch.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.command == "stop":
        config = _load_config(None)
        stop_file = getattr(config, "stop_file", "javis/watchdog/watchdog.stop")
        stop_path = Path(stop_file)
        stop_path.parent.mkdir(parents=True, exist_ok=True)
        stop_path.write_text("stop")
        print(f"Stop file created: {stop_path}")
        return 0


    return 1


def _load_config(path: Path | None) -> WatchdogConfig:
    """Load config from JSON file or return defaults."""
    if path is None or not path.exists():
        return WatchdogConfig()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return WatchdogConfig.from_dict(data)


if __name__ == "__main__":
    sys.exit(main())
