from fastapi import FastAPI

from app.database import Base, engine
from app.routes.certificates import router as certificates_router
from app.routes.jobs import router as jobs_router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Create and track bulk certificate generation jobs.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router)
app.include_router(certificates_router)