import logging

from rrs_connector.config import load_settings
from rrs_connector.logging_config import setup_logging

LOGGER = logging.getLogger(__name__)

def main() -> None:
    setup_logging()

    LOGGER.info("Starting rrs-connector")

    try:
        LOGGER.info("Loading configuration")
        env_settings, network_settings, senders_model = load_settings()
        LOGGER.info(env_settings.network_config_file)
        LOGGER.info("Configuration loaded successfully")
    except Exception:
        LOGGER.exception("Application startup failed")
        raise
    
    enabled_senders = sum(sender.enabled for sender in senders_model.senders)

    LOGGER.info(
        "Startup summary: network=%s, senders=%d, enabled_senders=%d, "
        "poll_interval_seconds=%d",
        network_settings.network,
        len(senders_model.senders),
        enabled_senders,
        env_settings.poll_interval_seconds,
    )

    LOGGER.info("Config files: network=%s, senders=%s",
        env_settings.network_config_file,
        env_settings.senders_config_file,
    )

if __name__ == "__main__":
    main()
