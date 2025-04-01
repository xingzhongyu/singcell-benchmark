# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import existing and new routers
from .routers import data, analysis
from .routers import integration, trajectory, communication # NEW

app = FastAPI(title="Scanpy Analysis API")

# --- CORS Middleware --- (Keep existing)
origins = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://211.87.232.159:3001" # Your frontend origin
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(data.router, prefix="/api/data", tags=["Data Upload & Base Results"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Basic Analysis Tasks"])
app.include_router(integration.router, prefix="/api/integration", tags=["Data Integration Tasks"]) # NEW
app.include_router(trajectory.router, prefix="/api/trajectory", tags=["Trajectory Analysis Tasks"]) # NEW
app.include_router(communication.router, prefix="/api/communication", tags=["Cell Communication Tasks"]) # NEW


# --- Root Endpoint --- (Keep existing)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Scanpy Analysis API!"}

# --- Startup Event (Optional) --- (Keep existing if using)

# --- (Optional) Create data directories on startup ---
# Handled in config.py now, but could be done here too.
# from .core.config import UPLOAD_DIR, RESULT_DIR
# @app.on_event("startup")
# async def startup_event():
#     UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
#     RESULT_DIR.mkdir(parents=True, exist_ok=True)