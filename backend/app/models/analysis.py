from pydantic import BaseModel
from typing import Optional, Dict, Any

class AnalysisParams(BaseModel):
    # Define parameters users can control
    min_genes: int = 200
    min_cells: int = 3
    pca_n_comps: int = 50
    neighbors_n_pcs: int = 30 # Use fewer PCs for neighbor graph
    leiden_resolution: float = 0.5

class TaskResponse(BaseModel):
    task_id: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None # Celery result (can be dict or error info)