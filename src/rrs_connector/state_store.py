from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.config import SenderConfig
from rrs_connector.db_models import DatalogEntryRecord, DatalogStatus, SenderRecord


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

    def add_datalog_entry(
        self,
        sender_id: int,
        datalog_index: int,
        raw_payload: str | None,
        cid: str | None,
        status: DatalogStatus,
        datalog_timestamp: datetime | None = None,
        error_message: str | None = None,
    ) -> bool:
        """
        Store one observed datalog entry.

        Returns True when a new row is inserted. Returns False when the
        sender/index pair already exists.
        """
        with self._session_factory() as session:
            sender_record = session.get(SenderRecord, sender_id)
            if sender_record is None:
                raise ValueError(f"Sender not found: {sender_id}")

            existing_entry = session.scalar(
                select(DatalogEntryRecord).where(
                    DatalogEntryRecord.sender_id == sender_id,
                    DatalogEntryRecord.datalog_index == datalog_index,
                )
            )

            if existing_entry is not None:
                return False

            datalog_entry_record = DatalogEntryRecord(
                sender_id=sender_id,
                datalog_index=datalog_index,
                datalog_timestamp=datalog_timestamp,
                raw_payload=raw_payload,
                cid=cid,
                status=status,
                error_message=error_message,
            )
            session.add(datalog_entry_record)
            session.commit()

            return True

    def get_datalog_entry_record(
        self,
        sender_id: int,
        datalog_index: int,
    ) -> DatalogEntryRecord | None:
        """Return one datalog entry by sender/index pair, if it exists."""

        with self._session_factory() as session:
            return session.scalar(
                select(DatalogEntryRecord).where(
                    DatalogEntryRecord.sender_id == sender_id,
                    DatalogEntryRecord.datalog_index == datalog_index,
                )
            )

    def list_datalog_entry_records_by_status(
        self,
        status: DatalogStatus,
    ) -> list[DatalogEntryRecord]:
        """Return datalog entries currently in the given processing status."""

        with self._session_factory() as session:
            stmt = (
                select(DatalogEntryRecord)
                .where(DatalogEntryRecord.status == status)
                .order_by(
                    DatalogEntryRecord.sender_id, DatalogEntryRecord.datalog_index
                )
            )
            return list(session.scalars(stmt).all())

    def mark_datalog_entry_status(
        self,
        entry_id: int,
        status: DatalogStatus,
        error_message: str | None = None,
    ) -> None:
        """Update processing status and optional error for one datalog entry."""

        with self._session_factory() as session:
            entry_record = session.get(DatalogEntryRecord, entry_id)

            if entry_record is None:
                raise ValueError(f"Datalog entry not found: {entry_id}")

            entry_record.status = status
            entry_record.error_message = error_message

            if status == DatalogStatus.PROCESSED:
                entry_record.processed_at = datetime.now(UTC)

            session.commit()

    def get_datalog_entry_record_by_id(
        self, entry_id: int
    ) -> DatalogEntryRecord | None:
        """Return one datalog entry by primary key, if it exists."""

        with self._session_factory() as session:
            return session.get(DatalogEntryRecord, entry_id)
