import logging
from dataclasses import dataclass

from rrs_connector.config import (
    ConnectorEnvSettings,
    ConnectorNetworkConfig,
    ConnectorSendersConfig,
)
from rrs_connector.db import (
    create_db_engine,
    create_session_factory,
    initialize_database,
)
from rrs_connector.state_store import StateStore

LOGGER = logging.getLogger(__name__)


@dataclass
class RunOnceResult:
    processed: int
    enabled: int
    failed: int
    skipped: int

    @property
    def exit_code(self) -> int:
        return 0 if self.failed == 0 else 3


def run_once(
    env_settings: ConnectorEnvSettings,
    network_settings: ConnectorNetworkConfig,
    senders_config: ConnectorSendersConfig,
) -> RunOnceResult:
    LOGGER.info("Starting run-once pass")

    engine = create_db_engine(env_settings.state_db)
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    store = StateStore(session_factory)
    store.sync_senders(senders_config.senders)

    total_senders = len(senders_config.senders)
    enabled_senders = sum(sender.enabled for sender in senders_config.senders)
    skipped_senders = total_senders - enabled_senders

    processed_senders = 0
    failed_senders = 0

    for sender in senders_config.senders:

        if not sender.enabled:
            continue

        try:
            LOGGER.info(
                "Sender ID: %s, address: %s, description: %s",
                sender.client_id,
                sender.robonomics_address,
                sender.description,
            )
            processed_senders += 1
        except Exception:
            LOGGER.exception(
                "Error during processing sender ID %s", sender.client_id
            )
            failed_senders += 1

    LOGGER.info(
        "Run once is completed, successfully processed %d out of %d senders, "
        "%d senders are failed, skipped=%d", 
        processed_senders,
        enabled_senders,
        failed_senders,
        skipped_senders
    )
    return RunOnceResult(
        processed_senders,
        enabled_senders,
        failed_senders,
        skipped_senders,
    )
