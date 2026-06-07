from app.db.base import Base
import app.models  # noqa: F401  # ensures models register on Base.metadata


def test_agents_table_registered():
    assert "agents" in Base.metadata.tables


def test_agents_table_has_expected_columns():
    columns = Base.metadata.tables["agents"].columns.keys()
    for expected in ["id", "name", "type", "status", "last_seen", "created_at", "updated_at"]:
        assert expected in columns
