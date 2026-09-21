from fastapi import APIRouter

from uribap_api.api.health import router as health_router
from uribap_api.api.households import router as households_router
from uribap_api.api.identity import router as identity_router
from uribap_api.api.ingredients import router as ingredients_router
from uribap_api.api.inventory import router as inventory_router
from uribap_api.api.invitations import router as invitations_router
from uribap_api.api.recipes import router as recipes_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(identity_router)
api_router.include_router(inventory_router)
api_router.include_router(households_router)
api_router.include_router(invitations_router)
api_router.include_router(ingredients_router)
api_router.include_router(recipes_router)
