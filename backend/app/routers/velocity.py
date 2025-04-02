# backend/app/routers/velocity.py
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult

from ..models.analysis import RnaVelocityParams, TaskResponse, TaskStatusResponse
from ..tasks.velocity_tasks import run_rna_velocity # Import the new task
from celery_app import celery_app
from ..core.config import RESULT_DIR, UPLOAD_DIR # Need UPLOAD_DIR to check original file

router = APIRouter()

@router.post("/start", response_model=TaskResponse, status_code=202, summary="Start RNA Velocity Analysis Task")
async def start_rna_velocity_analysis(params: RnaVelocityParams):
    """ Triggers the background RNA Velocity analysis task. """

    # --- Validation ---
    # 1. Check if the *original* uploaded file exists (velocity needs spliced/unspliced)
    source_adata_original_path = UPLOAD_DIR / f"{params.source_data_id}.h5ad"
    if not source_adata_original_path.exists():
        raise HTTPException(status_code=404, detail=f"Original data file for ID {params.source_data_id} not found in uploads directory. Velocity analysis requires the original file with spliced/unspliced layers.")

    # 2. Check if a *processed* file (e.g., with UMAP) exists for embedding overlay
    #    Velocity can run without it, but plotting might fail. Let task handle plot errors.
    source_adata_processed_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_processed.h5ad"
    source_adata_integrated_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_integrated.h5ad"
    if not source_adata_processed_path.exists() and not source_adata_integrated_path.exists():
         print(f"Warning: Processed/Integrated AnnData for ID {params.source_data_id} not found. Velocity calculations will run, but embedding plots might fail if basis '{params.embedding_basis}' is missing.")


    # Send task to Celery queue
    task = run_rna_velocity.delay(params.dict())
    return {"task_id": task.id}


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get RNA Velocity Task Status")
async def get_velocity_task_status(task_id: str):
    """ Checks the status of a submitted Celery RNA Velocity task. """
    task_result = AsyncResult(task_id, app=celery_app)
    # Reuse status checking logic
    status = task_result.status
    result = None
    if task_result.failed():
        status = "FAILURE"
        result = {"error": "Task failed", "details": str(task_result.info)}
    elif task_result.successful():
        status = "SUCCESS"
        result = task_result.get()
    elif status == 'PROGRESS':
        result = task_result.info
    elif status == 'STARTED':
        result = task_result.info
    elif status == 'PENDING':
        result = {'status': 'Task is waiting'}
    # ... handle other statuses ...
    return {"task_id": task_id, "status": status, "result": result}


# --- Result Endpoints ---
@router.get("/results/{source_data_id}/plot/velocity_embedding/{stream}", summary="Get Velocity Embedding Plot")
async def get_velocity_embedding_plot(
    source_data_id: str,
    stream: bool = False # Query parameter to get stream plot vs grid plot
    ):
    """ Serves the velocity embedding plot (grid or stream). """
    from ..routers.data import _get_result_path
    from fastapi.responses import FileResponse

    plot_suffix = "stream" if stream else "grid"
    # Plot name convention from the task (e.g., velocity_embedding_umap_grid.png)
    # Basis might be dynamic, needs careful handling. Assume fixed 'umap' for now or pass basis?
    basis = "umap" # Needs to match task output naming convention
    plot_filename = f"velocity_embedding_{basis}_{plot_suffix}.png"
    plot_path = _get_result_path(source_data_id, plot_filename) # Path within results dir
    return FileResponse(str(plot_path), media_type="image/png")


# Optional: Endpoint to download AnnData with velocity results
@router.get("/results/{source_data_id}/velocity_data", summary="Download AnnData with Velocity Results")
async def download_velocity_adata(source_data_id: str):
     """ Serves the AnnData file potentially updated with velocity results. """
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse

     # File name convention from the task (if save_updated_adata was True)
     adata_filename = f"{source_data_id}_velocity.h5ad"
     file_path = _get_result_path(source_data_id, adata_filename, check_exists=True)
     return FileResponse(
         str(file_path),
         media_type="application/octet-stream",
         filename=adata_filename
     )