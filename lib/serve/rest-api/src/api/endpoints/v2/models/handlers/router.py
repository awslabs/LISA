from fastapi import APIRouter
from . import create_model, get_model, list_models, delete_model

router = APIRouter(prefix='/models', tags=['model'])
router.include_router(create_model.router)
router.include_router(get_model.router)
router.include_router(list_models.router)
router.include_router(delete_model.router)