from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import homework
from app.routers import classes, notes, concepts, practice, plan, uploads
from app.routers import performance
# ✅ CREATE APP FIRST
app = FastAPI(title="College AI")

# ✅ MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ INCLUDE ROUTERS AFTER APP EXISTS
app.include_router(homework.router)
app.include_router(classes.router)
app.include_router(notes.router)
app.include_router(concepts.router)
app.include_router(practice.router)
app.include_router(plan.router)
app.include_router(uploads.router)
app.include_router(performance.router)
@app.get("/health")
async def health():
    return {"ok": True}
