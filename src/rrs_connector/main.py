import argparse
import logging
import sys

from rrs_connector.config import load_settings
from rrs_connector.logging_config import setup_logging
from rrs_connector.pipeline import RunOnceResult, run_once

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", type=str, choices=["run-once"], default="run-once")
    args = parser.parse_args()
    command = args.command

    setup_logging()

    LOGGER.info("Starting rrs-connector")

    try:
        LOGGER.info("Loading configuration")
        env_settings, network_settings, senders_model = load_settings()
    except Exception:
        LOGGER.exception("Application startup failed")
        return 1
    
    enabled_senders = sum(sender.enabled for sender in senders_model.senders)
    LOGGER.info(
        "Configuration: network=%s, senders=%d, enabled_senders=%d, "
        "poll_interval_seconds=%d",
        network_settings.network,
        len(senders_model.senders),
        enabled_senders,
        env_settings.poll_interval_seconds,
    )

    LOGGER.info(
        "Config files: network=%s, senders=%s",
        env_settings.network_config_file,
        env_settings.senders_config_file,
    )

    try:
        if command == "run-once":
            result: RunOnceResult = run_once(
                env_settings, network_settings, senders_model
            )
            return result.exit_code
    except Exception:
        LOGGER.exception("Application failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
