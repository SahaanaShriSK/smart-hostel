from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.api import (
    auth_router,
    student_router,
    warden_router,
    accountant_router,
    admin_router,
    common_router
)

app = FastAPI(
    title="SmartHostel API",
    description="Backend API for SmartHostel Management System - 5th Sem DBMS Project",
    version="1.0.0"
)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
custom_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *custom_origins,
    ],
    allow_origin_regex=r"https://.*\.azurewebsites\.net|https://.*\.azurestaticapps\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_router, prefix="/api")
app.include_router(student_router, prefix="/api")
app.include_router(warden_router, prefix="/api")
app.include_router(accountant_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(common_router, prefix="/api")

# Check for unified frontend static build in backend/static
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

if os.path.exists(static_dir) and os.path.exists(os.path.join(static_dir, "index.html")):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API or Swagger documentation routes
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json") or full_path.startswith("redoc"):
            raise HTTPException(status_code=404, detail="Not Found")
        
        file_path = os.path.join(static_dir, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(static_dir, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {
            "status": "online",
            "project": "SmartHostel",
            "description": "DBMS Stored Procedures & Triggers backed API Layer"
        }

