import logging
from dataclasses import dataclass

from rrs_connector.config import (
    ConnectorEnvSettings,
    ConnectorNetworkModel,
    ConnectorSendersModel,
)

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
    network_settings: ConnectorNetworkModel,
    senders_model: ConnectorSendersModel,
) -> RunOnceResult:
    LOGGER.info("Starting run-once pass")

    total_senders = len(senders_model.senders)
    enabled_senders = sum(sender.enabled for sender in senders_model.senders)
    skipped_senders = total_senders - enabled_senders

    processed_senders = 0
    failed_senders = 0

    for sender in senders_model.senders:

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
