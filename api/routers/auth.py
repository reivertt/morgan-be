# api/routers/auth.py
from ninja import Router, Schema
from ninja.errors import HttpError
from django.contrib.auth.models import User
from jwt.exceptions import ExpiredSignatureError
from ninja.errors import HttpError
from ninja_simple_jwt.auth.ninja_auth import HttpJwtAuth

router = Router()

class RegisterIn(Schema):
    username: str
    password: str

class RegisterOut(Schema):
    username: str

@router.post("register", response=RegisterOut)
def register(request, data: RegisterIn):
    if User.objects.filter(username=data.username).exists():
        raise HttpError(400, "Username already exists")
    user = User(username=data.username)
    user.set_password(data.password)
    user.save()
    return {"username": user.username}


class UserOut(Schema):
    username: str

@router.get("me", response=UserOut, auth=[HttpJwtAuth()])
def get_current_user(request):
    # pull the real User instance from request.user
    print(request)
    user = request.user
    if not user:
        raise HttpError(401, "Not authenticated")
    return {"username": user.username}
