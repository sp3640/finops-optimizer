import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events.
    """
    logger.info("FinOps Optimizer starting up...")
    yield
    logger.info("FinOps Optimizer shutting down.")


app = FastAPI(
    title       = "FinOps Cloud Cost Optimizer",
    description = "Multi-cloud waste detection — AWS + Azure",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# Enable CORS for local development (React/Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["http://localhost:3000", "http://localhost:5173"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# Include the scanning routes
app.include_router(
    scan.router,
    prefix = "/api/v1/scan",
    tags   = ["Scan"],
)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "finops-optimizer"}


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "FinOps Cloud Cost Optimizer API",
        "docs":    "/docs",
        "version": "1.0.0",
    }