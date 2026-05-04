from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.config import SenderConfig
from rrs_connector.db_models import SenderRecord


class StateStore:
    def __init__(self, session_factory) -> None:
        self._session_factory: sessionmaker[Session] = session_factory

    def sync_senders(self, sender_configs: Sequence[SenderConfig]) -> None:
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

            session.commit()
