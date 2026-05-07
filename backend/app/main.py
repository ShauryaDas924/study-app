from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.db import AsyncSessionLocal
from app.models import Note
from app.routers import homework
from app.routers import classes, notes, concepts, practice, plan, uploads
from app.routers import performance
from app.routers import exam_prep

app = FastAPI(title="College AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def reset_stale_extractions():
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Note)
            .where(Note.extraction_status.in_(["queued", "running"]))
            .values(
                extraction_status="idle",
                extraction_progress=0,
                extraction_error="Server restarted before extraction finished.",
            )
        )
        await db.commit()


app.include_router(homework.router)
app.include_router(classes.router)
app.include_router(notes.router)
app.include_router(concepts.router)
app.include_router(practice.router)
app.include_router(plan.router)
app.include_router(exam_prep.router)
app.include_router(uploads.router)
app.include_router(performance.router)


@app.get("/health")
async def health():
    return {"ok": True}
