# backend/app/routers/data.py
from typing import Literal
from fastapi import APIRouter, UploadFile, File, HTTPException, Path as FastApiPath, Query
from fastapi.responses import FileResponse, JSONResponse
import shutil
import uuid
import scanpy as sc # Needed for reading adata
import pandas as pd # Needed for reading marker CSV
from pathlib import Path
import traceback # For detailed error logging
import scipy.sparse as sp
from ..core.config import UPLOAD_DIR, RESULT_DIR

router = APIRouter()

@router.post("/upload", summary="Upload H5AD File")
async def upload_data(file: UploadFile = File(..., description="H5AD file to upload (.h5ad)")):
    # ...(no changes needed here) ...
    if not file.filename.endswith(".h5ad"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .h5ad files are accepted.")

    data_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{data_id}.h5ad"

    try:
        with upload_path.open("wb") as buffer:
           shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        await file.close()

    return {"data_id": data_id, "filename": file.filename}


# --- Result Retrieval Endpoints ---

def _get_result_path(data_id: str, filename: str, check_exists: bool = True) -> Path:
    """Helper to construct and check result file paths."""
    base_dir = RESULT_DIR / data_id
    if not base_dir.is_dir():
         raise HTTPException(status_code=404, detail=f"Result directory for data ID {data_id} not found. Analysis may not have started or failed early.")
    file_path = base_dir / filename
    if check_exists and not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Result file '{filename}' not found for data ID {data_id}. Analysis might be incomplete or the specific result was not generated.")
    return file_path

@router.get("/results/{data_id}/plot/umap/{cluster_method}", summary="Get UMAP Plot")
async def get_umap_plot(
    data_id: str = FastApiPath(..., description="Unique ID of the dataset"),
    cluster_method: str = FastApiPath(..., description="Clustering method used (e.g., 'leiden', 'louvain')")
    ):
    """ Serves the generated UMAP plot image based on clustering method. """
    plot_filename = f"umap_{cluster_method}.png"
    plot_path = _get_result_path(data_id, plot_filename)
    return FileResponse(str(plot_path), media_type="image/png")

@router.get("/results/{data_id}/plot/qc_violin", summary="Get QC Violin Plot")
async def get_qc_violin_plot(data_id: str = FastApiPath(..., description="Unique ID of the dataset")):
    """ Serves the QC violin plot generated before filtering. """
    plot_path = _get_result_path(data_id, "qc_violin_before_filter.png")
    return FileResponse(str(plot_path), media_type="image/png")

@router.get("/results/{data_id}/processed_data", summary="Download Processed AnnData")
async def get_processed_data(data_id: str = FastApiPath(..., description="Unique ID of the dataset")):
    """ Serves the processed AnnData (.h5ad) file for download. """
    file_path = _get_result_path(data_id, f"{data_id}_processed.h5ad")
    return FileResponse(
        str(file_path),
        media_type="application/octet-stream",
        filename=f"{data_id}_processed.h5ad"
    )

@router.get("/results/{data_id}/marker_genes/{cluster_method}", summary="Get Marker Genes Table")
async def get_marker_genes_table(
    data_id: str = FastApiPath(..., description="Unique ID of the dataset"),
    cluster_method: str = FastApiPath(..., description="Clustering method used for markers"),
    format: Literal['csv', 'json'] = Query('json', description="Output format: 'csv' or 'json'")
    ):
    """ Retrieves marker genes, either as a downloadable CSV or JSON data. """
    csv_filename = f"marker_genes_{cluster_method}.csv"
    csv_path = _get_result_path(data_id, csv_filename)

    if format == 'csv':
        return FileResponse(
            str(csv_path),
            media_type="text/csv",
            filename=csv_filename
        )
    elif format == 'json':
        try:
            df = pd.read_csv(csv_path)
            # Convert to JSON suitable for frontend (e.g., list of records)
            # Handle potential NaN values gracefully for JSON serialization
            json_data = df.where(pd.notnull(df), None).to_dict(orient='records')
            return JSONResponse(content=json_data)
        except Exception as e:
             trace = traceback.format_exc()
             print(f"Error reading/converting marker CSV {csv_path}: {e}\n{trace}")
             raise HTTPException(status_code=500, detail=f"Failed to process marker gene file: {e}")

@router.get("/results/{data_id}/gene_expression/{gene_name}", summary="Get UMAP Coords and Gene Expression")
async def get_gene_expression_data(
    data_id: str = FastApiPath(..., description="Unique ID of the dataset"),
    gene_name: str = FastApiPath(..., description="Name of the gene to retrieve expression for")
    ):
    """
    Loads the processed AnnData, extracts UMAP coordinates and expression
    for a specific gene, returning them as JSON.
    """
    adata_path = _get_result_path(data_id, f"{data_id}_processed.h5ad")
    try:
        adata = sc.read_h5ad(adata_path)

        # Check if gene exists
        if gene_name not in adata.var_names:
            # Try case-insensitive match as fallback? (Optional)
            # matching_genes = [g for g in adata.var_names if g.lower() == gene_name.lower()]
            # if not matching_genes:
            raise HTTPException(status_code=404, detail=f"Gene '{gene_name}' not found in the processed data's variable names.")
            # gene_name = matching_genes[0] # Use the actual name if found case-insensitively

        # Check if UMAP was computed
        if 'X_umap' not in adata.obsm:
             raise HTTPException(status_code=404, detail="UMAP coordinates ('X_umap') not found in the processed data.")

        # Extract data
        umap_coords = adata.obsm['X_umap'].tolist() # Convert numpy array to list for JSON
        # Accessing expression: Use .X which should be log-normalized counts
        # Need to handle sparse matrices if .X is sparse
    
        if isinstance(adata.X, sp.csc_matrix) or isinstance(adata.X, sp.csr_matrix):
             expression = adata[:, gene_name].X.toarray().flatten().tolist()
        else:
             # Find the index of the gene
             gene_index = adata.var_names.get_loc(gene_name)
             expression = adata.X[:, gene_index].flatten().tolist()


        # Get cluster assignments for potential coloring/hover info
        clusters = adata.obs['clusters'].tolist() if 'clusters' in adata.obs else None

        return JSONResponse(content={
            "gene_name": gene_name,
            "umap_coordinates": umap_coords,
            "expression": expression,
            "clusters": clusters,
            "cell_ids": adata.obs_names.tolist() # Include cell IDs
        })

    except FileNotFoundError:
         raise HTTPException(status_code=404, detail=f"Processed data file not found: {adata_path.name}")
    except KeyError as ke:
         raise HTTPException(status_code=404, detail=f"Data key not found: {ke}. Check if analysis step completed.")
    except Exception as e:
        trace = traceback.format_exc()
        print(f"Error loading or processing AnnData {adata_path} for gene {gene_name}: {e}\n{trace}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve gene expression data: {e}")