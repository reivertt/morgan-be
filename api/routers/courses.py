# backend/api/routers/courses.py

from typing import List
from ninja import Router, Schema
from ninja.errors import HttpError
from django.http import HttpResponse
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth
from api.models import Course

router = Router(
    tags=["courses"],
    auth=[HttpJwtAuth()],    
)

class CourseIn(Schema):
    name: str

class CourseOut(CourseIn):
    id: int
    owner: str
    created_at: str

@router.get("", response=List[CourseOut])
def list_courses(request):
    user = request.user
    qs = Course.objects.filter(owner_id=user.id).order_by("-created_at")
    return [
        {
            "id": c.id,
            "name": c.name,
            "owner": c.owner.username,
            "created_at": c.created_at.isoformat(),
        }
        for c in qs
    ]

@router.post("", response=CourseOut)
def create_course(request, data: CourseIn):
    user = request.user
    c = Course.objects.create(name=data.name, owner_id=user.id)
    return {
        "id": c.id,
        "name": c.name,
        "owner": c.owner.username,
        "created_at": c.created_at.isoformat(),
    }

@router.patch("/{course_id}", response=CourseOut)
def update_course(request, course_id: int, data: CourseIn):
    user = request.user
    try:
        c = Course.objects.get(id=course_id, owner_id=user.id)
    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")
    c.name = data.name
    c.save()
    return {
        "id": c.id,
        "name": c.name,
        "owner": c.owner.username,
        "created_at": c.created_at.isoformat(),
    }

@router.delete("/{course_id}")
def delete_course(request, course_id: int):
    user = request.user
    deleted, _ = Course.objects.filter(id=course_id, owner_id=user.id).delete()
    if not deleted:
        raise HttpError(404, "Course not found")
    return HttpResponse(status=204)

@router.get("/{course_id}", response=CourseOut)
def get_course(request, course_id: int):
    user = request.user
    try:
        c = Course.objects.get(id=course_id, owner_id=user.id)
    except Course.DoesNotExist:
        raise HttpError(404, "Course not found")
    return {
        "id": c.id,
        "name": c.name,
        "owner": c.owner.username,
        "created_at": c.created_at.isoformat(),
    }