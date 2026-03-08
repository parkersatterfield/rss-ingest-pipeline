from __future__ import annotations

import argparse
import logging
import time

from pipeline import IngestPipeline
from settings import load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Continuously ingest RSS content into Qdrant"
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set log verbosity",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config()
    pipeline = IngestPipeline(config)

    while True:
        pipeline.run_cycle()
        if args.once:
            break
        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
