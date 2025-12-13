# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import existing and new routers
from .routers import data, analysis
from .routers import integration, trajectory, communication,velocity,atac # NEW
from .routers import deepsem  # Proxy to DeepSEM service

app = FastAPI(title="Scanpy Multi-Modal Analysis API")

# --- CORS Middleware --- (Keep existing)
origins = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://211.87.232.159:3001", # Your frontend origin
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://211.87.232.159:3002", # Your frontend origin
    "http://sdu-159:3002"
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
app.include_router(analysis.router, prefix="/api/analysis", tags=["Basic RNA Analysis Tasks"])
app.include_router(atac.router, prefix="/api/atac", tags=["ATAC Analysis Tasks (Muon)"]) # NEW Router & Tag
app.include_router(integration.router, prefix="/api/integration", tags=["Data Integration Tasks"]) # NEW
app.include_router(trajectory.router, prefix="/api/trajectory", tags=["Trajectory Analysis Tasks"]) # NEW
app.include_router(communication.router, prefix="/api/communication", tags=["Cell Communication Tasks"]) # NEW
app.include_router(velocity.router, prefix="/api/velocity", tags=["RNA Velocity Tasks"]) # NEW
app.include_router(deepsem.router, prefix="/api/deepsem", tags=["DeepSEM GRN"])


# --- Root Endpoint --- (Keep existing)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Scanpy Analysis API!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# --- Startup Event (Optional) --- (Keep existing if using)

# --- (Optional) Create data directories on startup ---
# Handled in config.py now, but could be done here too.
# from .core.config import UPLOAD_DIR, RESULT_DIR
# @app.on_event("startup")
# async def startup_event():
#     UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
#     RESULT_DIR.mkdir(parents=True, exist_ok=True)