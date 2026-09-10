from app.routers.companies import router as companies_router
from app.routers.departments import router as departments_router
from app.routers.employees import router as employees_router
from app.routers.goals import router as goals_router
from app.routers.policies import router as policies_router
from app.routers.documents import router as documents_router
from app.routers.memory import router as memory_router
from app.routers.coo import router as coo_router
from app.routers.agents import router as agents_router
from app.routers.company_state import router as company_state_router
from app.routers.events import router as events_router
from app.routers.decisions import router as decisions_router
from app.routers.tasks import router as tasks_router
from app.routers.notifications import router as notifications_router
from app.routers.purchase_requests import router as purchase_requests_router
from app.routers.reports import router as reports_router
from app.routers.calendar_events import router as calendar_events_router

__all__ = [
    "companies_router",
    "departments_router",
    "employees_router",
    "goals_router",
    "policies_router",
    "documents_router",
    "memory_router",
    "coo_router",
    "agents_router",
    "company_state_router",
    "events_router",
    "decisions_router",
    "tasks_router",
    "notifications_router",
    "purchase_requests_router",
    "reports_router",
    "calendar_events_router",
]
