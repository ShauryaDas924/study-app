
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

    resp = await client.chat.completions.create(
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


# ------------------------
# MAIN ROUTER FUNCTION
# ------------------------
async def extract_text(filename: str, file_bytes: bytes) -> str:
    filename = filename.lower()

    if filename.endswith((".png", ".jpg", ".jpeg")):
        if USE_VISION:
            return await extract_from_image(file_bytes)
        else:
            return "Vision disabled"

    if filename.endswith(".pdf"):
        return extract_from_pdf(file_bytes)

    if filename.endswith((".pptx", ".ppt")):
        return extract_from_ppt(file_bytes)

    return "Unsupported file type"


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
