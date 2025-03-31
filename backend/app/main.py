from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import data, analysis # Import routers

app = FastAPI(title="Scanpy Analysis API")

# --- CORS Middleware ---
# Adjust origins as needed for production
origins = [
    "http://localhost:3001", # Default React dev server
    "http://127.0.0.1:3001",
    "http://211.87.232.159:3001"
    # Add your frontend deployment URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Include Routers ---
app.include_router(data.router, prefix="/api/data", tags=["Data Upload & Results"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis Tasks"])

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Scanpy Analysis API!"}

# --- (Optional) Create data directories on startup ---
# Handled in config.py now, but could be done here too.
# from .core.config import UPLOAD_DIR, RESULT_DIR
# @app.on_event("startup")
# async def startup_event():
#     UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
#     RESULT_DIR.mkdir(parents=True, exist_ok=True)