# backend/app/routers/atac.py
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult

from ..models.analysis import AtacAnalysisParams, TaskResponse, TaskStatusResponse
from ..tasks.atac_tasks import run_atac_analysis # Import the new task
from celery_app import celery_app
from ..core.config import UPLOAD_DIR, RESULT_DIR

router = APIRouter()

@router.post("/start", response_model=TaskResponse, status_code=202, summary="Start ATAC Analysis Task (Muon)")
async def start_atac_analysis(params: AtacAnalysisParams):
    """ Triggers the background ATAC-seq analysis task using Muon. """

    # --- Validation ---
    # Check if the source ATAC file exists in uploads
    source_adata_path = UPLOAD_DIR / f"{params.source_data_id}.h5ad"
    if not source_adata_path.exists():
        raise HTTPException(status_code=404, detail=f"Source ATAC data file for ID {params.source_data_id} not found in uploads directory.")

    # Ensure result directory will exist (task should create specific subdir)
    result_base_dir = RESULT_DIR / params.source_data_id
    # result_base_dir.mkdir(parents=True, exist_ok=True) # Task will handle this

    # Send task to Celery queue
    task = run_atac_analysis.delay(params.dict())
    return {"task_id": task.id}


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get ATAC Analysis Task Status")
async def get_atac_task_status(task_id: str):
    """ Checks the status of a submitted Celery ATAC analysis task. """
    task_result = AsyncResult(task_id, app=celery_app)
    # Reuse status checking logic from other routers
    status = task_result.status
    result = None
    if task_result.failed():
        status = "FAILURE"
        result = {"error": "Task failed", "details": str(task_result.info)}
    elif task_result.successful():
        status = "SUCCESS"
        result = task_result.get()
    elif status == 'PROGRESS': result = task_result.info
    elif status == 'STARTED': result = task_result.info
    elif status == 'PENDING': result = {'status': 'Task is waiting'}
    return {"task_id": task_id, "status": status, "result": result}


# --- Result Endpoints ---
# Add endpoints similar to other analyses to retrieve plots and processed data

@router.get("/results/{source_data_id}/plot/atac_umap", summary="Get ATAC UMAP Plot")
async def get_atac_umap_plot(source_data_id: str, color_by: str = "clusters"):
    """ Serves the ATAC UMAP plot colored by clusters or other obs key. """
    from ..routers.data import _get_result_path
    from fastapi.responses import FileResponse
    # Plot name convention from task (e.g., atac_umap_clusters.png)
    # Needs careful coordination with task output naming
    plot_filename = f"atac_umap_{color_by}.png"
    plot_path = _get_result_path(source_data_id, plot_filename, check_exists=True)
    return FileResponse(str(plot_path), media_type="image/png")

@router.get("/results/{source_data_id}/plot/atac_qc", summary="Get ATAC QC Violin Plot")
async def get_atac_qc_plot(source_data_id: str):
    """ Serves the ATAC QC violin plot. """
    from ..routers.data import _get_result_path
    from fastapi.responses import FileResponse
    plot_filename = "atac_qc_violin.png" # Convention from task
    plot_path = _get_result_path(source_data_id, plot_filename, check_exists=True)
    return FileResponse(str(plot_path), media_type="image/png")


@router.get("/results/{source_data_id}/processed_atac_data", summary="Download Processed ATAC AnnData")
async def download_processed_atac_data(source_data_id: str):
     """ Serves the processed ATAC AnnData file. """
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse
     # File name convention from task
     adata_filename = f"{source_data_id}_processed_atac.h5ad"
     file_path = _get_result_path(source_data_id, adata_filename, check_exists=True)
     return FileResponse(str(file_path), media_type="application/octet-stream", filename=adata_filename)