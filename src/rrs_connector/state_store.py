from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.config import SenderConfig
from rrs_connector.db_models import SenderRecord


class StateStore:
    """Persistence API for connector runtime state."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Store a factory used to open short-lived database sessions."""

        self._session_factory = session_factory

    def sync_senders(self, sender_configs: Sequence[SenderConfig]) -> None:
        """Synchronize sender config into local state.

        The sender registry config is the source of truth for active sender
        configuration. Existing records are updated, new records are created,
        and records missing from the current config are disabled instead of
        deleted to preserve cursors and future report history.
        """

        with self._session_factory() as session:
            for sender_config in sender_configs:
                sender_record = session.scalar(
                    select(SenderRecord).where(
                        SenderRecord.robonomics_address
                        == sender_config.robonomics_address
                    )
                )
                if sender_record is None:
                    sender_record = SenderRecord(
                        client_id=sender_config.client_id,
                        robonomics_address=sender_config.robonomics_address,
                        description=sender_config.description,
                        enabled=sender_config.enabled,
                    )
                    session.add(sender_record)
                else:
                    sender_record.client_id = sender_config.client_id
                    sender_record.description = sender_config.description
                    sender_record.enabled = sender_config.enabled

            configured_addresses = {
                sender_config.robonomics_address for sender_config in sender_configs
            }

            records_to_disable = session.scalars(
                select(SenderRecord).where(
                    SenderRecord.robonomics_address.not_in(configured_addresses),
                    SenderRecord.enabled.is_(True),
                )
            ).all()

            for sender_record in records_to_disable:
                sender_record.enabled = False

            session.commit()

    def get_enabled_sender_records(self) -> list[SenderRecord]:
        """Return sender records that should be polled."""

        with self._session_factory() as session:
            stmt = (
                select(SenderRecord)
                .where(SenderRecord.enabled.is_(True))
                .order_by(SenderRecord.id)
            )
            return list(session.scalars(stmt).all())

    def get_sender_record_by_address(self, address: str) -> SenderRecord | None:
        """Return one sender record by Robonomics address, if it exists."""

        with self._session_factory() as session:
            stmt = select(SenderRecord).where(
                SenderRecord.robonomics_address == address
            )
            return session.scalar(stmt)

    def mark_sender_scanned(self, sender_id: int, datalog_index: int) -> None:
        """Move a sender datalog cursor to the last scanned index."""

        with self._session_factory() as session:
            sender_record = session.get(SenderRecord, sender_id)

            if sender_record is None:
                raise ValueError(f"Sender not found: {sender_id}")

            sender_record.last_scanned_datalog_index = datalog_index
            sender_record.last_scanned_at = datetime.now(UTC)

            session.commit()
