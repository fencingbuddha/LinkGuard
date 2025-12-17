from fastapi import FastAPI
from app.api.analyze import router as analyze_router
from app.init_db import init_db
from app.api.admin import router as admin_router

app = FastAPI()

@app.on_event("startup")
def _startup() -> None:
    init_db()

app.include_router(analyze_router)
app.include_router(admin_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}