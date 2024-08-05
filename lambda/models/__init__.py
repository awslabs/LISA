from fastapi import APIRouter, FastAPI

router = APIRouter(prefix='/models', tags=['model']) 

# import routes after defining router
from .routes import *

app = FastAPI()
app.include_router(router)