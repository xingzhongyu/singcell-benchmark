from fastapi import APIRouter, UploadFile, File, HTTPException, Path as FastApiPath
from fastapi.responses import FileResponse
import shutil
import uuid
from pathlib import Path

from ..core.config import UPLOAD_DIR, RESULT_DIR

router = APIRouter()

@router.post("/upload", summary="Upload H5AD File")
async def upload_data(file: UploadFile = File(..., description="H5AD file to upload")):
    if not file.filename.endswith(".h5ad"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .h5ad files are accepted.")

    # Generate a unique ID for this dataset
    data_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{data_id}.h5ad"

    try:
        # Asynchronously save the uploaded file
        with upload_path.open("wb") as buffer:
           shutil.copyfileobj(file.file, buffer)
           # If using aiofiles:
           # async with aiofiles.open(upload_path, 'wb') as out_file:
           #     content = await file.read() # Read content chunk by chunk for large files if needed
           #     await out_file.write(content)

    except Exception as e:
        # Basic error handling
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        await file.close() # Ensure the file is closed

    return {"data_id": data_id, "filename": file.filename}


@router.get("/results/{data_id}/umap", summary="Get UMAP Plot")
async def get_umap_plot(data_id: str = FastApiPath(..., description="Unique ID of the dataset")):
    """
    Serves the generated UMAP plot image.
    Assumes the plot is saved as 'umap_leiden.png' in the result directory.
    """
    plot_path = RESULT_DIR / data_id / "umap_leiden.png"

    if not plot_path.exists():
        raise HTTPException(status_code=404, detail="UMAP plot not found. Analysis might not be complete or failed.")

    return FileResponse(str(plot_path), media_type="image/png")

# Add more endpoints here later to retrieve other results (tables, processed data file, etc.)
# Example:
# @router.get("/results/{data_id}/processed_data")
# async def get_processed_data(data_id: str):
#     file_path = RESULT_DIR / data_id / f"{data_id}_processed.h5ad"
#     if not file_path.exists():
#         raise HTTPException(status_code=404, detail="Processed data file not found.")
#     return FileResponse(str(file_path), media_type="application/octet-stream", filename=f"{data_id}_processed.h5ad")