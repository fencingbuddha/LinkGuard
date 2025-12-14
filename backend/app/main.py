from fastapi import FastAPI
from app.api.analyze import router as analyze_router

app = FastAPI()

app.include_router(analyze_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}