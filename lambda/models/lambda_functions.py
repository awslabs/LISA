from fastapi import FastAPI
from .routes.router import router
from mangum import Mangum

app = FastAPI()
app.include_router(router)

handler = Mangum(app, lifespan="off")