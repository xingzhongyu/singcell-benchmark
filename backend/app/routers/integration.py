from typing import Literal
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from celery.result import AsyncResult
import uuid

from ..models.analysis import IntegrationParams, TaskResponse, TaskStatusResponse
from ..tasks.integration_tasks import run_integration # Import the new task
from celery_app import celery_app
from ..core.config import UPLOAD_DIR, RESULT_DIR

router = APIRouter()

@router.post("/start", response_model=TaskResponse, status_code=202, summary="Start Data Integration Task")
async def start_integration_analysis(params: IntegrationParams):
    """ Triggers the background data integration task. """

    # Basic validation: Check if input files exist
    for f_info in params.files:
        adata_path = UPLOAD_DIR / f"{f_info.data_id}.h5ad"
        if not adata_path.exists():
            raise HTTPException(status_code=404, detail=f"Input data file with ID {f_info.data_id} not found.")

    # Generate output ID if not provided
    output_data_id = params.output_data_id or str(uuid.uuid4())

    # Ensure output directory doesn't clash unexpectedly (optional check)
    output_dir = RESULT_DIR / output_data_id
    if output_dir.exists() and any(output_dir.iterdir()): # Check if not empty
         print(f"Warning: Output directory {output_dir} already exists and is not empty.")
         # Decide on behavior: overwrite, error, or allow? For now, allow.

    # Send task to Celery queue
    task = run_integration.delay(output_data_id, params.dict())

    return {"task_id": task.id}

# Reuse the status endpoint logic (or create a shared utility)
@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get Integration Task Status")
async def get_integration_task_status(task_id: str):
    """ Checks the status of a submitted Celery integration task. """
    task_result = AsyncResult(task_id, app=celery_app)
    # ... (Copy logic from app/routers/analysis.py get_task_status or refactor) ...
    status = task_result.status
    result = None
    if task_result.failed():
        status = "FAILURE"
        result = {"error": "Task failed", "details": str(task_result.info)}
    elif task_result.successful():
         status = "SUCCESS"
         result = task_result.get()
    # ... handle other statuses (PENDING, STARTED, PROGRESS) ...
    return {"task_id": task_id, "status": status, "result": result}

# Add endpoints later to get integration-specific results (plots, integrated data)
# similar to how results are served in routers/data.py
@router.get("/results/{integrated_data_id}/plot/umap/{color_by}", summary="Get Integrated UMAP Plot")
async def get_integrated_umap_plot(integrated_data_id: str, color_by: Literal['batch', 'clusters'] = 'batch'):
     from ..routers.data import _get_result_path # Reuse helper
     from fastapi.responses import FileResponse
     plot_filename = f"umap_integrated_{color_by}.png"
     plot_path = _get_result_path(integrated_data_id, plot_filename)
     return FileResponse(str(plot_path), media_type="image/png")

# Endpoint to download integrated data
@router.get("/results/{integrated_data_id}/integrated_data", summary="Download Integrated AnnData")
async def get_integrated_adata(integrated_data_id: str):
     from ..routers.data import _get_result_path # Reuse helper
     from fastapi.responses import FileResponse
     file_path = _get_result_path(integrated_data_id, f"{integrated_data_id}_integrated.h5ad")
     return FileResponse(
         str(file_path),
         media_type="application/octet-stream",
         filename=f"{integrated_data_id}_integrated.h5ad"
     )