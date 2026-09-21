from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.forecast_schemas import DemandForecastResponse
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.application.forecast_service import demand_forecast
from uribap_api.domain.forecast.policies import DemandForecastError
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

router = APIRouter(prefix="/forecast", tags=["forecast"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


@router.get("/demand", response_model=DemandForecastResponse, responses=ERROR_RESPONSES)
def demand_forecast_route(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> DemandForecastResponse:
    effective_from = from_date or date.today()
    effective_to = to_date or (effective_from + timedelta(days=6))
    try:
        return demand_forecast(session, membership, effective_from, effective_to)
    except DemandForecastError as exc:
        raise DomainError("validation_failed", "Validation failed", str(exc), 422) from exc
