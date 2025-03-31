from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Path as FastApiPath
from celery.result import AsyncResult

from ..models.analysis import AnalysisParams, TaskResponse, TaskStatusResponse
from ..tasks.scanpy_tasks import run_scanpy_analysis # Import the task
from celery_app import celery_app # Import celery app instance
from ..core.config import UPLOAD_DIR

router = APIRouter()

@router.post("/analyze/{data_id}", response_model=TaskResponse, status_code=202, summary="Start Scanpy Analysis")
async def start_analysis(
    params: AnalysisParams, # Receive parameters from request body
    data_id: str = FastApiPath(..., description="Unique ID of the uploaded dataset")
):
    """
    Triggers the background Scanpy analysis task.
    """
    adata_path = UPLOAD_DIR / f"{data_id}.h5ad"
    if not adata_path.exists():
        raise HTTPException(status_code=404, detail=f"Data file with ID {data_id} not found.")

    # Send task to Celery queue
    # Pass params as a dictionary
    task = run_scanpy_analysis.delay(data_id, params.dict())

    return {"task_id": task.id}


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get Analysis Task Status")
async def get_task_status(task_id: str = FastApiPath(..., description="ID of the background task")):
    """
    Checks the status of a submitted Celery task.
    """
    task_result = AsyncResult(task_id, app=celery_app)

    status = task_result.status
    result = None

    if task_result.failed():
        status = "FAILURE" # Be explicit
        result = {
            "error": "Task failed",
            "details": str(task_result.info) # Get traceback/exception info
            }
    elif task_result.successful():
         status = "SUCCESS"
         result = task_result.get() # Get the return value of the task
    elif status == 'PENDING':
         result = {'status': 'Task is waiting to be processed'}
    elif status == 'STARTED':
         result = task_result.info # Get meta data if set by update_state
    elif status == 'PROGRESS':
         result = task_result.info # Get meta data from update_state

    # Ensure result is JSON serializable if it's not already handled
    # (Celery usually handles basic types, dicts, lists)

    return {"task_id": task_id, "status": status, "result": result}