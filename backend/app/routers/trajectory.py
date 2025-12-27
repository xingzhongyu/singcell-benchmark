from typing import Literal
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult

from ..models.analysis import TrajectoryParams, TaskResponse, TaskStatusResponse
from ..tasks.trajectory_tasks import run_trajectory_analysis # Import the new task
from celery_app import celery_app
from ..core.config import RESULT_DIR

router = APIRouter()

@router.post("/start", response_model=TaskResponse, status_code=202, summary="Start Trajectory Analysis Task")
async def start_trajectory_analysis(params: TrajectoryParams):
    """ Triggers the background trajectory analysis task. """
    # Validate source data exists
    source_adata_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_processed.h5ad"
    # Also check for integrated data if applicable? Logic might need refinement based on workflow.
    # For now, assume _processed exists.
    if not source_adata_path.exists():
         alt_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_integrated.h5ad"
         if not alt_path.exists():
              raise HTTPException(status_code=404, detail=f"Source data file for ID {params.source_data_id} (_processed.h5ad or _integrated.h5ad) not found.")


    task = run_trajectory_analysis.delay(params.dict())
    return {"task_id": task.id}


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get Trajectory Task Status")
async def get_trajectory_task_status(task_id: str):
    """ Checks the status of a submitted Celery trajectory task. """
    task_result = AsyncResult(task_id, app=celery_app)
    
    try:
        status = task_result.status
    except ValueError as e:
        # Handle corrupted task metadata (e.g., missing exc_type in exception info)
        return {
            "task_id": task_id,
            "status": "FAILURE",
            "result": {
                "error": "Task status corrupted",
                "details": f"Unable to decode task status: {str(e)}. The task may have failed with improperly stored exception information."
            }
        }
    
    result = None
    
    try:
        if task_result.failed():
            status = "FAILURE"
            try:
                result = {"error": "Task failed", "details": str(task_result.info)}
            except (ValueError, KeyError) as e:
                result = {
                    "error": "Task failed",
                    "details": f"Task failed but exception details could not be retrieved: {str(e)}"
                }
        elif task_result.successful():
             status = "SUCCESS"
             result = task_result.get()
        elif status == 'PENDING':
             result = {'status': 'Task is waiting to be processed'}
        elif status == 'STARTED':
             result = task_result.info
        elif status == 'PROGRESS':
             result = task_result.info
    except (ValueError, KeyError) as e:
        return {
            "task_id": task_id,
            "status": "FAILURE",
            "result": {
                "error": "Task metadata corrupted",
                "details": f"Unable to decode task information: {str(e)}"
            }
        }
    
    return {"task_id": task_id, "status": status, "result": result}


# Add endpoints for trajectory plots (Diffmap, PAGA, etc.)
@router.get("/results/{source_data_id}/plot/diffmap", summary="Get Diffusion Map Plot")
async def get_diffmap_plot(source_data_id: str):
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse
     plot_path = _get_result_path(source_data_id, "diffmap.png") # Assuming fixed name from task
     return FileResponse(str(plot_path), media_type="image/png")

@router.get("/results/{source_data_id}/plot/paga/{plot_type}", summary="Get PAGA Plot")
async def get_paga_plot(source_data_id: str, plot_type: Literal['graph', 'umap_embedding']):
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse
     plot_filename = f"paga_{plot_type}.png" # Assuming fixed names from task
     plot_path = _get_result_path(source_data_id, plot_filename)
     return FileResponse(str(plot_path), media_type="image/png")

# Add endpoint for pseudotime UMAP if calculated?
@router.get("/results/{source_data_id}/plot/umap/dpt", summary="Get UMAP colored by DPT")
async def get_dpt_umap_plot(source_data_id: str):
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse
     plot_path = _get_result_path(source_data_id, "umap_dpt_pseudotime.png", check_exists=False) # Check optional result
     if not plot_path.exists():
         raise HTTPException(status_code=404, detail="DPT UMAP plot not found. DPT might not have been calculated or plot generation failed.")
     return FileResponse(str(plot_path), media_type="image/png")