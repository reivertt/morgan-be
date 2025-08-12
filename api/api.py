from ninja import NinjaAPI
from .routers import items
from .routers import auth
from .routers import courses
from ninja_simple_jwt.auth.views.api import mobile_auth_router
from .routers import topics

api = NinjaAPI()

# Example API
api.add_router("/items/", items.router)
api.add_router("/auth/", auth.router)
api.add_router("/auth/", mobile_auth_router)
api.add_router("/courses/", courses.router)
api.add_router("/", topics.router)