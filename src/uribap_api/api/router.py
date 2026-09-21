from fastapi import APIRouter

from uribap_api.api.forecast import router as forecast_router
from uribap_api.api.health import router as health_router
from uribap_api.api.households import router as households_router
from uribap_api.api.identity import router as identity_router
from uribap_api.api.ingredients import router as ingredients_router
from uribap_api.api.inventory import router as inventory_router
from uribap_api.api.invitations import router as invitations_router
from uribap_api.api.plans import router as plans_router
from uribap_api.api.preparation import router as preparation_router
from uribap_api.api.completion import plans_router as completion_plans_router
from uribap_api.api.completion import router as completion_router
from uribap_api.api.recipes import router as recipes_router
from uribap_api.api.shopping import router as shopping_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(identity_router)
api_router.include_router(inventory_router)
api_router.include_router(households_router)
api_router.include_router(invitations_router)
api_router.include_router(ingredients_router)
api_router.include_router(recipes_router)
api_router.include_router(plans_router)
api_router.include_router(forecast_router)
api_router.include_router(shopping_router)
api_router.include_router(preparation_router)
api_router.include_router(completion_plans_router)
api_router.include_router(completion_router)
