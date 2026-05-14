
import base64
from openai import OpenAI
from PIL import Image
import fitz  # PyMuPDF
from pptx import Presentation
from io import BytesIO
from dotenv import load_dotenv
import os
import re
USE_VISION = True
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ------------------------
# VISION LLM
# ------------------------
async def extract_from_image(file_bytes: bytes) -> str:
    b64 = base64.b64encode(file_bytes).decode()

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all notes clearly. Preserve math."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}"
                        },
                    },
                ],
            }
        ],
    )

    return resp.choices[0].message.content


# ------------------------
# PDF
# ------------------------
def extract_from_pdf(file_bytes: bytes) -> str:
    text = ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    for page in doc:
        text += page.get_text()

    return text


# ------------------------
# PDF (MATH MODE OCR)
# ------------------------
async def extract_from_pdf_math(file_bytes: bytes) -> str:

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""

    for page in doc:

        page_text = page.get_text()

        # If page likely contains formulas or OCR artifacts
        if len(page_text) < 200 or "  " in page_text:

            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")

            vision_text = await extract_from_image(img_bytes)

            text += vision_text + "\n"

        else:
            text += page_text + "\n"

    return text

# ------------------------
# PPT
# ------------------------
def extract_from_ppt(file_bytes: bytes) -> str:
    prs = Presentation(BytesIO(file_bytes))
    text = ""

    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"

    return text


def extract_from_plain_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


# ------------------------
# MAIN ROUTER FUNCTION
# ------------------------
async def extract_text(filename: str, file_bytes: bytes, math_mode: bool = False) -> str:
    print("MATH MODE:", math_mode)
    filename = filename.lower()

    if filename.endswith((".png", ".jpg", ".jpeg")):
        if USE_VISION:
            return await extract_from_image(file_bytes)
        else:
            return "Vision disabled"

    if filename.endswith(".pdf"):

        if math_mode:
            return await extract_from_pdf_math(file_bytes)

        return extract_from_pdf(file_bytes)

    if filename.endswith((".pptx", ".ppt")):
        return extract_from_ppt(file_bytes)

    if filename.endswith((".txt", ".md")):
        return extract_from_plain_text(file_bytes)

    return "Unsupported file type"


async def extract_text_with_source(filename: str, file_bytes: bytes, math_mode: bool = False) -> dict:
    """
    Extract text while keeping lightweight source metadata for exam-prep evidence.
    Existing callers should keep using extract_text; this helper is additive.
    """
    original_filename = filename or "uploaded_material"
    lower = original_filename.lower()

    if lower.endswith(".pdf"):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        full_text_parts = []

        for index, page in enumerate(doc, start=1):
            page_text = page.get_text()

            if math_mode and (len(page_text or "") < 200 or "  " in (page_text or "")):
                pix = page.get_pixmap(dpi=300)
                page_text = await extract_from_image(pix.tobytes("png"))

            page_text = str(page_text or "").strip()
            if page_text:
                pages.append(
                    {
                        "page": index,
                        "start_char": sum(len(part) + 1 for part in full_text_parts),
                        "text": page_text,
                    }
                )
                full_text_parts.append(f"[Page {index}]\n{page_text}")

        return {
            "text": "\n\n".join(full_text_parts).strip(),
            "pages": pages,
            "source_ref": {
                "filename": original_filename,
                "page_count": len(doc),
                "extraction_mode": "pdf_pages",
            },
        }

    text = await extract_text(original_filename, file_bytes, math_mode=math_mode)
    return {
        "text": text,
        "pages": [],
        "source_ref": {
            "filename": original_filename,
            "extraction_mode": "single_text_block",
        },
    }


# ------------------------
# HOMEWORK QUESTION SPLITTER
# ------------------------



def split_homework_questions(text: str):

    # Splits on patterns like:
    # 1)
    # 1.
    # Question 1
    # Q1

    pattern = r"(?:^|\n)(?:Question\s*\d+|\d+\)|\d+\.)"

    parts = re.split(pattern, text)

    questions = []

    for p in parts:
        p = p.strip()

        if len(p) > 20:
            questions.append(p)

    return questions
