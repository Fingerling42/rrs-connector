import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.config import SenderConfig, SenderRegistryConfig
from rrs_connector.db import (
    create_db_engine,
    create_session_factory,
    initialize_database,
)
from rrs_connector.db_models import SenderRecord
from rrs_connector.state_store import StateStore

ADDRESS_1 = "4DVyLjBGM99Np9XBhADqkbTw9JGn2LgnFpHAQ8TBSjGPZ5fN"
ADDRESS_2 = "4Ff5w7XuzrfnuMT25GYijtu3w2DoRbjNSBgym4TRgPSh279f"
ADDRESS_3 = "4CrE2aFEXYeBrNJePkTPxF363NqYYvXC1PhWsSZWtbWy3PzJ"


@pytest.fixture
def sender_configs() -> list[SenderConfig]:
    senders_data = {
        "senders": [
            {
                "client_id": "1",
                "robonomics_address": ADDRESS_1,
                "description": "test_description1",
                "enabled": True,
            },
            {
                "client_id": "2",
                "robonomics_address": ADDRESS_2,
                "description": "test_description2",
                "enabled": True,
            },
            {
                "client_id": "3",
                "robonomics_address": ADDRESS_3,
                "description": "test_description3",
                "enabled": False,
            },
        ]
    }
    return SenderRegistryConfig.model_validate(senders_data).senders


@pytest.fixture
def session_factory(tmp_path) -> sessionmaker[Session]:
    db_path = tmp_path / "state.sqlite3"
    engine = create_db_engine(db_path)
    initialize_database(engine)
    return create_session_factory(engine)


@pytest.fixture
def store(session_factory: sessionmaker[Session]) -> StateStore:
    return StateStore(session_factory)


def get_sender_record(
    session: Session,
    address: str,
) -> SenderRecord | None:
    return session.scalar(
        select(SenderRecord).where(SenderRecord.robonomics_address == address)
    )


def assert_sender_matches_config(
    sender_record: SenderRecord | None,
    sender_config: SenderConfig,
) -> None:
    assert sender_record is not None
    assert sender_record.client_id == sender_config.client_id
    assert sender_record.robonomics_address == sender_config.robonomics_address
    assert sender_record.description == sender_config.description
    assert sender_record.enabled == sender_config.enabled
    assert sender_record.created_at is not None
    assert sender_record.updated_at is not None


def test_sync_senders_creates_senders(
    store: StateStore,
    session_factory: sessionmaker[Session],
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    with session_factory() as session:
        records = session.scalars(select(SenderRecord)).all()

        assert len(records) == len(sender_configs)

        for sender_config in sender_configs:
            sender_record = get_sender_record(
                session,
                sender_config.robonomics_address,
            )
            assert_sender_matches_config(sender_record, sender_config)


def test_sync_senders_updates_existing_senders(
    store: StateStore,
    session_factory: sessionmaker[Session],
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    sender_configs[0].description = "test_description1_new"
    sender_configs[0].enabled = False

    store.sync_senders(sender_configs)

    with session_factory() as session:
        records = session.scalars(select(SenderRecord)).all()
        updated_sender = get_sender_record(session, ADDRESS_1)

        assert len(records) == len(sender_configs)
        assert_sender_matches_config(updated_sender, sender_configs[0])


def test_sync_senders_preserves_sender_cursor(
    store: StateStore,
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    sender = store.get_sender_record_by_address(ADDRESS_1)
    assert sender is not None

    store.mark_sender_scanned(sender.id, 42)

    sender_configs[0].description = "test_description1_new"
    store.sync_senders(sender_configs)

    updated = store.get_sender_record_by_address(ADDRESS_1)
    assert updated is not None
    assert updated.description == "test_description1_new"
    assert updated.last_scanned_datalog_index == 42
    assert updated.last_scanned_at is not None


def test_get_enabled_sender_records(
    store: StateStore,
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    records = store.get_enabled_sender_records()

    assert [record.robonomics_address for record in records] == [
        ADDRESS_1,
        ADDRESS_2,
    ]


def test_get_sender_record_by_address(
    store: StateStore,
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    sender = store.get_sender_record_by_address(ADDRESS_1)

    assert sender is not None
    assert sender.robonomics_address == ADDRESS_1


def test_mark_sender_scanned_updates_cursor(
    store: StateStore,
    sender_configs: list[SenderConfig],
) -> None:
    store.sync_senders(sender_configs)

    sender = store.get_sender_record_by_address(ADDRESS_1)
    assert sender is not None

    store.mark_sender_scanned(sender.id, 42)

    updated = store.get_sender_record_by_address(ADDRESS_1)
    assert updated is not None
    assert updated.last_scanned_datalog_index == 42
    assert updated.last_scanned_at is not None


def test_mark_sender_scanned_raises_for_unknown_sender(
    store: StateStore,
) -> None:
    with pytest.raises(ValueError, match="Sender not found"):
        store.mark_sender_scanned(999, 42)


def test_sync_senders_disables_missing_senders(store, sender_configs):
    store.sync_senders(sender_configs)

    store.sync_senders(sender_configs[1:])

    missing_sender = store.get_sender_record_by_address(ADDRESS_1)

    assert missing_sender is not None
    assert missing_sender.enabled is False
