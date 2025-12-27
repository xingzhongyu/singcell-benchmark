from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
import zipfile # For zipping results
from pathlib import Path
from fastapi.responses import StreamingResponse
from ..models.analysis import CellCommunicationParams, TaskResponse, TaskStatusResponse
from ..tasks.communication_tasks import run_cellphone_analysis # Import the new task
from celery_app import celery_app
from ..core.config import RESULT_DIR

router = APIRouter()

@router.post("/start", response_model=TaskResponse, status_code=202, summary="Start Cell Communication Analysis Task")
async def start_cellphone_analysis(params: CellCommunicationParams):
    """ Triggers the background CellPhoneDB analysis task. """
     # Validate source data exists
    source_adata_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_processed.h5ad"
    alt_path = RESULT_DIR / params.source_data_id / f"{params.source_data_id}_integrated.h5ad"
    if not source_adata_path.exists() and not alt_path.exists():
        raise HTTPException(status_code=404, detail=f"Source data file for ID {params.source_data_id} not found.")

    # Basic check for database path (more robust checks might be needed)
    if params.cellphonedb_database_path is not None and not Path(params.cellphonedb_database_path).is_dir():
         # This path should likely come from backend config/env vars, not user input directly!
         # For now, raise error if provided path is invalid.
         raise HTTPException(status_code=400, detail=f"CellPhoneDB database path not found or invalid: {params.cellphonedb_database_path}")

    task = run_cellphone_analysis.delay(params.dict())
    return {"task_id": task.id}

@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="Get Cell Communication Task Status")
async def get_communication_task_status(task_id: str):
    """ Checks the status of a submitted Celery CellPhoneDB task. """
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

# Add endpoints for communication results (plots, raw files)
@router.get("/results/{source_data_id}/plot/cellphonedb/{plot_name}", summary="Get CellPhoneDB Plot")
async def get_cellphonedb_plot(source_data_id: str, plot_name: str):
     # Example: plot_name could be "dot_plot.png" or "heatmap.png"
     from ..routers.data import _get_result_path
     from fastapi.responses import FileResponse
     # Construct path based on convention from task (e.g., inside the output suffix dir)
     # Suffix might be dynamic from params, need careful handling
     # For simplicity, assume fixed plot names within the main result dir for now
     # This needs refinement based on task output structure.
     output_suffix = "cellphonedb_out" # Example: Get this from task result or params if dynamic
     plot_path = _get_result_path(source_data_id, f"{output_suffix}/{plot_name}.png", check_exists=True)
     return FileResponse(str(plot_path), media_type="image/png")


@router.get("/results/{source_data_id}/download/cellphonedb", summary="Download CellPhoneDB Results Archive")
async def download_cellphonedb_results(source_data_id: str):
    from ..routers.data import _get_result_path
    from fastapi.responses import FileResponse
    import io

    # Output path convention needs to be solid from the task
    # Let's assume the task saves results in 'cellphonedb_out' inside the data_id dir
    # And the SUCCESS result contains the path to this dir
    # This endpoint logic might need task result info or fixed paths

    output_suffix = "cellphonedb_out" # Get this dynamically if needed
    cpdb_output_dir = _get_result_path(source_data_id, output_suffix, check_exists=True)

    zip_buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for entry in cpdb_output_dir.rglob('*'): # Recursively find all files
                if entry.is_file():
                    zip_file.write(entry, entry.relative_to(cpdb_output_dir))
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to create zip archive: {e}")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type='application/zip',
        headers={"Content-Disposition": f"attachment; filename={source_data_id}_cellphonedb_results.zip"}
    )