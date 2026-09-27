from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys
import time
from typing import Optional

from coach import Coach
from config import Config
from local_store import LocalStore
from telegram_api import TelegramAPI


LOG = logging.getLogger(__name__)


def log_directory(config_path: Optional[str], database_path: str) -> Path:
    if config_path:
        storage_dir = Path(config_path).expanduser().parent
    else:
        storage_dir = Path(database_path).expanduser().parent
    return storage_dir / "logs"


def configure_logging(config_path: Optional[str], database_path: str) -> None:
    log_dir = log_directory(config_path, database_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "service.log", maxBytes=2_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram certification study agent")
    parser.add_argument(
        "--config",
        help="Optional JSON config path. Environment variables take precedence.",
    )
    args = parser.parse_args()
    config = Config.load(args.config)
    configure_logging(args.config, config.database_path)
    store = LocalStore(config.database_path)
    store.cleanup()
    api = TelegramAPI(config.telegram_token, timeout=20)
    api.delete_webhook()
    api.set_commands()
    coach = Coach(config, store, api)

    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="study-generator")
    generation: Optional[Future] = None
    generation_slot: Optional[str] = None
    retry_after = 0.0
    offset = None
    failures = 0
    LOG.info("Certification study agent started")
    try:
        while running:
            if generation is not None and generation.done():
                try:
                    succeeded = bool(generation.result())
                    retry_after = 0.0 if succeeded else time.monotonic() + 300
                except Exception:
                    LOG.exception("Background study generation failed")
                    retry_after = time.monotonic() + 300
                generation = None
            slot = coach.current_slot()
            active_exam_id = store.active_exam().id
            should_attempt = (
                slot
                and not store.is_paused()
                and generation is None
                and not store.has_slot(active_exam_id, slot)
                and (slot != generation_slot or time.monotonic() >= retry_after)
            )
            if should_attempt:
                generation_slot = slot
                generation = executor.submit(coach.send_study_set, slot)
            try:
                updates = api.get_updates(offset=offset, timeout=20)
                failures = 0
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    try:
                        coach.handle_update(update)
                    except Exception:
                        LOG.exception("Failed to process Telegram update")
            except Exception:
                failures += 1
                LOG.exception("Telegram polling failed")
                time.sleep(min(60, 2 ** min(failures, 5)))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        LOG.info("Certification study agent stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
