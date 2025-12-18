from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.analyze import router as analyze_router
from app.api.admin import router as admin_router
from app.api.admin_orgs import router as admin_orgs_router
from app.init_db import init_db
from app.api.admin_stats import router as admin_stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

# Allow the Vite dev server (dashboard) to call the API during local development.
# This also enables proper handling of browser CORS preflight (OPTIONS) requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # includes Authorization
)


app.include_router(analyze_router)
app.include_router(admin_router)
app.include_router(admin_orgs_router)
app.include_router(admin_stats_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}