from typing import cast

from sqlalchemy import Table, UniqueConstraint

from uribap_api.infrastructure.persistence.mcp_models import McpToken


def test_mcp_token_metadata_matches_existing_unique_constraint_and_index() -> None:
    table = cast(Table, McpToken.__table__)
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name == "uq_mcp_token_hash"
    ]
    assert len(constraints) == 1
    assert [column.name for column in constraints[0].columns] == ["token_hash"]

    indexes = [index for index in table.indexes if index.name == "ix_mcp_token_token_hash"]
    assert len(indexes) == 1
    assert indexes[0].unique is True
    assert [column.name for column in indexes[0].columns] == ["token_hash"]
