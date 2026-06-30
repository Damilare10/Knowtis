"""
Main FastAPI Application Entrypoint
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth_routes, events_routes

app = FastAPI(
    title="Knowtis API",
    description="AI-powered academic communication assistant backend",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_routes.router)
app.include_router(events_routes.router)


@app.on_event("startup")
def on_startup():
    """Create database tables on startup if they do not exist"""
    from app.database import engine, Base
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)



@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/status")
async def system_status():
    """System status endpoint with minimal metadata"""
    return {
        "status": "online",
        "version": "0.1.0",
        "service": "Knowtis Backend Service"
    }
