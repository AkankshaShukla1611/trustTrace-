from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import datasets, projects, runs, test_cases
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TrustTrace API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(datasets.router)
app.include_router(test_cases.router)
