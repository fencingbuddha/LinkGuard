from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.analyze import router as analyze_router
from app.api.admin import router as admin_router
from app.api.admin_orgs import router as admin_orgs_router
from app.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


app.include_router(analyze_router)
app.include_router(admin_router)
app.include_router(admin_orgs_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}