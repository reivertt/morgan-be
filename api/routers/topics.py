# backend/api/routers/topics.py

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

class SummaryOut(Schema):
    summary: str

class TopicOut(Schema):
    id: int
    name: str
    file_url: str
    created_at: str
    progress: int

class TopicNameOut(Schema):
    id: int
    name: str
    created_at: str

@router.get("/courses/{course_id}/topics", response=List[TopicOut])
def list_topics(request, course_id: int):
    user = request.user
    if not user:
        raise HttpError(401, "Not authenticated")

    try:
        course = Course.objects.get(id=course_id, owner_id=user.id)
    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")

    return [
        {
            "id":          t.id,
            "name":        t.name,
            "file_url":    request.build_absolute_uri(t.file.url),
            "created_at":  t.created_at.isoformat(),
            "progress": t.progress
        }
        for t in course.topics.order_by("-created_at")
    ]


@router.post("/courses/{course_id}/topics", response=TopicOut)
def create_topic(
    request,
    course_id: int,
    name: str            = Form(...),
    file: UploadedFile   = File(...),
):
    user = request.user
    if not user:
        raise HttpError(401, "Not authenticated")
    try:
        course = Course.objects.get(id=course_id, owner_id=request.user.id)
    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")

    # 1) create the Topic without a file → has a valid .pk
    topic = Topic.objects.create(course=course, name=name)

    # 2) now save the file so upload_to sees topic.pk
    topic.file.save(file.name, file, save=True)

    return {
        "id":         topic.id,
        "name":       topic.name,
        "file_url":   request.build_absolute_uri(topic.file.url),
        "created_at": topic.created_at.isoformat(),
    }


@router.patch("/topics/{topic_id}", response=TopicOut)
def update_topic(
    request,
    topic_id: int,
    name: str            = Form(None),
    file: UploadedFile   = File(None),
):
    user = request.user
    if not user:
        raise HttpError(401, "Not authenticated")
    try:
        topic = Topic.objects.get(id=topic_id, course__owner_id=request.user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if name is not None:
        topic.name = name
    if file is not None:
        # this will again call upload_to with the existing topic.pk
        topic.file.save(file.name, file, save=True)

    topic.save()
    return {
        "id":         topic.id,
        "name":       topic.name,
        "file_url":   request.build_absolute_uri(topic.file.url),
        "created_at": topic.created_at.isoformat(),
    }


@router.delete(
    "/topics/{topic_id}",
    response={204: None},
)
def delete_topic(request, topic_id: int):
    user = request.user
    if not user:
        raise HttpError(401, "Not authenticated")

    deleted, _ = Topic.objects.filter(
        id=topic_id, course__owner_id=user.id
    ).delete()

    if not deleted:
        raise HttpError(404, "Topic not found")
    # return a 204 No Content
    return 204, None

@router.get("/topics/{topic_id}", response=TopicNameOut)
def get_topics(request, topic_id: int):
    user = request.user
    try:
        t = Topic.objects.get(id=topic_id, course__owner_id=request.user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Course not found")
    return {
        "id": t.id,
        "name": t.name,
        "created_at": t.created_at.isoformat(),
    }

def clean_text(text: str) -> str:
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    lines = text.splitlines()
    kept = []
    for L in lines:
        if re.fullmatch(r'[\W_]{3,}', L):
            continue
        if re.fullmatch(r'(.)\1{5,}', L):
            continue
        kept.append(L)
    cleaned = "\n".join(kept)
    return re.sub(r'\n{3,}', "\n\n", cleaned)

def chunk_text(text: str, max_lines: int = 200) -> List[str]:
    lines = text.splitlines()
    return [
        "\n".join(lines[i : i + max_lines])
        for i in range(0, len(lines), max_lines)
        if lines[i : i + max_lines]
    ]

@router.get("/topics/{topic_id}/summary", response=SummaryOut)
def summarize_topic(request, topic_id: int):
    user = request.user
    try:
        topic = Topic.objects.get(id=topic_id, course__owner_id=user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if not topic.file:
        raise HttpError(400, "No file attached")

    # Download PDF and extract raw text
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

    chunks = chunk_text(full_text, max_lines=200)
    if not chunks:
        raise HttpError(500, "Could not chunk text")

    partials: List[str] = []
    for c in chunks:
        try:
            resp = groq_client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are an expert lecturer. Read the following excerpt and turn it into a structured study note:
- Start with a brief heading.
- Include definitions of all key terms.
- Show any formulas (with names) and label variables if there is any.
- Illustrate with the concrete example given.
- Return _only_ well-formatted note text (no extra commentary).
- RETURN ONLY THE NOTE NO ADDED (INTRO OR OUTRO) TEXT
"""
                    },
                    {"role": "user", "content": c},
                ],
                max_tokens=512,
                temperature=0.3,
            )
            partials.append(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.exception("GROQ chunk error")
            raise HttpError(502, f"GROQ chunk: {e}")

    # Merge partial summaries in batches
    def batch(xs, n): return [xs[i:i+n] for i in range(0, len(xs), n)]
    merged: List[str] = []
    for grp in batch(partials, 5):
        payload = "\n\n".join(grp)
        try:
            m = groq_client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are an expert lecturer. Combine these segment notes into one cohesive set of study notes:
- Organize under clear headings.
- Preserve formulas (if there is any) and examples.
- Use bullet points where helpful.
- Return _only_ the merged study notes.
- RETURN ONLY THE NOTE NO ADDED (INTRO OR OUTRO) TEXT
"""
                    },
                    {"role": "user", "content": payload},
                ],
                max_tokens=512,
                temperature=0.3,
            )
            merged.append(m.choices[0].message.content.strip())
        except Exception as e:
            logger.exception("GROQ merge error")
            raise HttpError(502, f"GROQ merge: {e}")

    # Final merge
    all_payload = "\n\n".join(merged)
    try:
        final = groq_client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {
                    "role": "system",
                    "content": """
You are an expert lecturer. Combine these segment notes into one cohesive set of study notes:
- Organize under clear headings.
- Preserve formulas (if there is any) and examples.
- Use bullet points where helpful.
- Return _only_ the merged study notes.
- RETURN ONLY THE NOTE NO ADDED (INTRO OR OUTRO) TEXT
"""
                },
                {"role": "user", "content": all_payload},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        overall = final.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("GROQ final error")
        raise HttpError(502, f"GROQ final: {e}")

    return {"summary": overall}

class FlashcardsOut(Schema):
    flashcards: List[str]


@router.get("/topics/{topic_id}/flashcards", response=FlashcardsOut)
def generate_flashcards(request, topic_id: int):
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

    chunks = chunk_text(full_text, max_lines=200)
    if not chunks:
        raise HttpError(500, "Could not chunk text")

    flashcard_parts: List[str] = []

    for c in chunks:
        try:
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
  Q: ...
  A: ...
- Return 10 cards.
- Return only the flashcards, no extra text.
- Please make it such the question is a term of the content and the answer is the definition or explanation.
"""
                    },
                    {"role": "user", "content": c},
                ],
                max_tokens=512,
                temperature=0.4,
            )
            flashcard_parts.append(flashcard_resp.choices[0].message.content.strip())
        except Exception as e:
            logger.exception("GROQ chunk error (flashcard)")
            raise HttpError(502, f"GROQ chunk error: {e}")

    all_flashcards_text = "\n\n".join(flashcard_parts)

    # Optional: clean and split flashcards to structured list
    flashcards = [fc.strip() for fc in re.split(r'\n\s*\n', all_flashcards_text) if fc.strip()]

    return {
        "flashcards": flashcards,
    }

class QuizOut(Schema):
    Quiz: List[str]


@router.get("/topics/{topic_id}/quiz", response=QuizOut)
def generate_quiz(request, topic_id: int):
    user = request.user
    try:
        topic = Topic.objects.get(id=topic_id, course__owner_id=user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if not topic.file:
        raise HttpError(400, "No file attached")

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

    chunks = chunk_text(full_text, max_lines=500)
    if not chunks:
        raise HttpError(500, "Could not chunk text")

    quiz_parts: List[str] = []

    for c in chunks:
        try:
            # Generate flashcards (Q&A pairs)
            quiz_resp = groq_client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are a helpful AI tutor. Extract key concepts and generate quiz:
- Each problem should be a simple Q&A with multiple choice answer.
- Keep questions concise and factual.
- Format:
  Q: ...
  Choices:
    A. ...
    B. ...
    C. ...
    D. ...
  Answer:
    A (correct answer)
- Return 15 problems.
- Return only the problems, no extra text.
"""
                    },
                    {"role": "user", "content": c},
                ],
                max_tokens=512,
                temperature=0.4,
            )
            quiz_parts.append(quiz_resp.choices[0].message.content.strip())
        except Exception as e:
            logger.exception("GROQ chunk error (flashcard)")
            raise HttpError(502, f"GROQ chunk error: {e}")

    all_quiz_text = "\n\n".join(quiz_parts)

    # Optional: clean and split flashcards to structured list
    Quiz = [fc.strip() for fc in re.split(r'\n\s*\n', all_quiz_text) if fc.strip()]

    return {
        "Quiz": Quiz,
    }

class ProgressIn(Schema):
    progress: int

@router.patch("/topics/{topic_id}/progress", response={200: dict})
def update_progress(request, topic_id: int, data: ProgressIn):
    user = request.user
    try:
        topic = Topic.objects.get(id=topic_id, course__owner_id=user.id)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    topic.completion_percentage = data.progress
    topic.save()
    return {"message": "Progress updated", "progress": topic.completion_percentage}