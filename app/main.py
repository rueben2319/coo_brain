import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    companies_router,
    departments_router,
    employees_router,
    goals_router,
    policies_router,
    documents_router,
    memory_router,
    coo_router,
    agents_router,
    company_state_router,
    events_router,
    decisions_router,
    tasks_router,
    notifications_router,
    purchase_requests_router,
    reports_router,
    calendar_events_router,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coo_brain")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting COO Brain backend in [{settings.environment}] mode")
    logger.info(f"Connected Supabase: {settings.supabase_url}")
    logger.info(f"Embedding model: {settings.ollama_embed_model} (dim={settings.vector_dimension})")
    logger.info(f"Chat model: {settings.ollama_chat_model}")
    yield
    logger.info("COO Brain backend shutting down")


app = FastAPI(
    title="Executive COO Brain Backend API",
    description="Multi-tenant executive advisory intelligence backend with vector retrieval over pgvector and Ollama LLM.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "coo_brain",
        "environment": settings.environment,
        "models": {
            "chat": settings.ollama_chat_model,
            "embed": settings.ollama_embed_model,
            "vector_dim": settings.vector_dimension,
        },
    }


# Register all routers
app.include_router(companies_router)
app.include_router(departments_router)
app.include_router(employees_router)
app.include_router(goals_router)
app.include_router(policies_router)
app.include_router(documents_router)
app.include_router(memory_router)
app.include_router(coo_router)
app.include_router(agents_router)
app.include_router(company_state_router)
app.include_router(events_router)
app.include_router(decisions_router)
app.include_router(tasks_router)
app.include_router(notifications_router)
app.include_router(purchase_requests_router)
app.include_router(reports_router)
app.include_router(calendar_events_router)

