import requests, fitz
from typing import List
from ninja import Router, Schema, Form, File, UploadedFile
from ninja.errors import HttpError
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from api.models import Topic, Course
from django.conf import settings
import logging
import os
from groq import Groq, APIStatusError, APIConnectionError
import re

router = Router(tags=["topics"], auth=[HttpJwtAuth()])
logger = logging.getLogger(__name__)
groq_client = Groq()

class QuizAndFlashcardsOut(Schema):
    quiz: str
    flashcards: List[str]


@router.get("/topics/{topic_id}/quiz-flashcards", response=QuizAndFlashcardsOut)
def generate_quiz_and_flashcards(request, topic_id: int):
    user = request.user
    try:
        topic = Topic.objects.get(id=topic_id, course__owner_id=user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if not topic.file:
        raise HttpError(400, "No file attached")

    # Step 1: Extract and clean PDF text
    pdf_url = request.build_absolute_uri(topic.file.url)
    try:
        resp = requests.get(pdf_url, timeout=15); resp.raise_for_status()
        doc = fitz.open(stream=resp.content, filetype="pdf")
        raw = "\n".join(p.get_text() for p in doc)
    except Exception as e:
        logger.exception("PDF extract failed")
        raise HttpError(502, f"PDF read error: {e}")

    full_text = clean_text(raw)
    if not full_text.strip():
        raise HttpError(500, "No usable text")

    chunks = chunk_text(full_text, max_lines=150)
    if not chunks:
        raise HttpError(500, "Could not chunk text")

    quiz_parts: List[str] = []
    flashcard_parts: List[str] = []

    for c in chunks:
        try:
            # Generate quiz questions
            quiz_resp = groq_client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are a helpful AI tutor. Create a short quiz from this content:
- Include 3–5 questions.
- Use a mix of question types (MCQs, short answer, true/false).
- Do not include answers.
- Format:
  Q1: What is ...?
  A. ...
  B. ...
"""
                    },
                    {"role": "user", "content": c},
                ],
                max_tokens=512,
                temperature=0.4,
            )
            quiz_parts.append(quiz_resp.choices[0].message.content.strip())

            # Generate flashcards (Q&A pairs)
            flashcard_resp = groq_client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are a helpful AI tutor. Extract key concepts and generate flashcards:
- Each card should be a simple Q&A.
- Keep questions concise and factual.
- Format:
  Q: What is ...?
  A: ...
- Return 5–7 cards.
"""
                    },
                    {"role": "user", "content": c},
                ],
                max_tokens=512,
                temperature=0.4,
            )
            flashcard_parts.append(flashcard_resp.choices[0].message.content.strip())
        except Exception as e:
            logger.exception("GROQ chunk error (quiz or flashcard)")
            raise HttpError(502, f"GROQ chunk error: {e}")

    # Step 2: Merge both types
    all_quiz = "\n\n".join(quiz_parts)
    all_flashcards_text = "\n\n".join(flashcard_parts)

    # Optional: clean and split flashcards to structured list
    flashcards = [fc.strip() for fc in re.split(r'\n\s*\n', all_flashcards_text) if fc.strip()]

    return {
        "quiz": all_quiz,
        "flashcards": flashcards,
    }
