


from app.models import Note
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.llm import refine_notes
from app.models import Concept
from app.models import NoteConcept
from app.services.file_extraction import extract_text
from app.services.llm import (
    extract_concepts_from_note,
    generate_flashcards_from_concepts,
    client
)
from app.services.llm import classify_concept_role, assign_card_budget
from fastapi import Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.services.auth import get_current_user_id
from uuid import UUID
from app.models import Flashcard
from app.models import FlashcardState
from datetime import datetime
from sqlalchemy import select
router = APIRouter(prefix="/upload", tags=["upload"])




@router.post("/notes")
async def upload_note(
    file: UploadFile = File(...),
    class_id: UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user_id = Depends(get_current_user_id)
):
    content = await file.read()
    raw_text = await extract_text(file.filename, content)
    text = await refine_notes(raw_text)

    return {
        "filename": file.filename,
        "extracted_text": text,
        "flashcards": []
    }
