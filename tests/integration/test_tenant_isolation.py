from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser


@pytest.mark.integration
def test_membership_query_is_scoped_to_household(integration_engine) -> None:
    user_id = uuid4()
    household_id = uuid4()
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        session.add(Household(id=household_id, name="Isolation", locale="es", timezone="UTC"))
        session.add(
            HouseholdMember(
                household_id=household_id,
                user_id=user_id,
                role=MembershipRole.MEMBER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.commit()
        rows = session.scalars(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user_id,
            )
        ).all()
        assert len(rows) == 1
