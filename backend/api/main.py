from fastapi import FastAPI
from backend.ingestion.upload import router as upload_router
from backend.api.jobs import router as jobs_router
from backend.api.enrichment import router as enrichment_router

app = FastAPI(title="Flowstate API")

app.include_router(upload_router)
app.include_router(jobs_router)
app.include_router(enrichment_router)

@app.get("/")
def root():
    return {"status": "Flowstate is running"}
