import scanpy as sc
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path

from ..core.config import UPLOAD_DIR_STR, RESULT_DIR_STR # Use config paths
from celery_app import celery_app # Import the app instance

# Define base directory for figures if needed, relative to RESULT_DIR
FIGURE_DIR_TEMP = Path(RESULT_DIR_STR) / "temp_figures"
FIGURE_DIR_TEMP.mkdir(parents=True, exist_ok=True)
sc.settings.figdir = str(FIGURE_DIR_TEMP) # Tell Scanpy where to save temporary figures

@celery_app.task(bind=True)
def run_scanpy_analysis(self, data_id: str, params: dict):
    """
    Celery task to perform basic Scanpy analysis.
    params is expected to be a dict derived from AnalysisParams model.
    """
    adata_path = os.path.join(UPLOAD_DIR_STR, f"{data_id}.h5ad")
    result_data_dir = Path(RESULT_DIR_STR) / data_id
    result_data_dir.mkdir(parents=True, exist_ok=True)

    processed_adata_path = result_data_dir / f"{data_id}_processed.h5ad"
    umap_plot_path = result_data_dir / "umap_leiden.png"

    try:
        self.update_state(state='STARTED', meta={'status': 'Loading data...'})
        adata = sc.read_h5ad(adata_path)

        self.update_state(state='PROGRESS', meta={'status': 'Filtering...'})
        sc.pp.filter_cells(adata, min_genes=params.get('min_genes', 200))
        sc.pp.filter_genes(adata, min_cells=params.get('min_cells', 3))

        self.update_state(state='PROGRESS', meta={'status': 'Normalizing and Logarithmizing...'})
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

        # Optional: HVG - good practice but adds time
        # self.update_state(state='PROGRESS', meta={'status': 'Finding Highly Variable Genes...'})
        # sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
        # adata = adata[:, adata.var.highly_variable].copy() # Subset to HVGs

        self.update_state(state='PROGRESS', meta={'status': 'Running PCA...'})
        sc.tl.pca(adata, svd_solver='arpack', n_comps=params.get('pca_n_comps', 50))

        self.update_state(state='PROGRESS', meta={'status': 'Calculating Neighbors...'})
        # Use fewer PCs for neighbors calculation is common practice
        n_pcs_neighbors = min(params.get('neighbors_n_pcs', 30), adata.obsm['X_pca'].shape[1])
        sc.pp.neighbors(adata, n_neighbors=10, n_pcs=n_pcs_neighbors)

        self.update_state(state='PROGRESS', meta={'status': 'Running UMAP...'})
        sc.tl.umap(adata)

        self.update_state(state='PROGRESS', meta={'status': 'Running Leiden Clustering...'})
        sc.tl.leiden(adata, resolution=params.get('leiden_resolution', 0.5))

        # --- Generate and Save Results ---
        self.update_state(state='PROGRESS', meta={'status': 'Generating UMAP plot...'})

        # Define a unique filename for the plot to avoid conflicts if tasks run concurrently
        temp_plot_filename = f"umap_{data_id}_{uuid.uuid4()}.png"
        sc.pl.umap(adata, color=['leiden'], save=f"_{temp_plot_filename}", show=False, title=f"Leiden (res={params.get('leiden_resolution', 0.5)})")

        # Construct the expected temporary path Scanpy used
        scanpy_saved_path = FIGURE_DIR_TEMP / f"umap_{temp_plot_filename}"

        # Move the plot from Scanpy's temp figdir to the final result location
        if scanpy_saved_path.exists():
            scanpy_saved_path.rename(umap_plot_path)
            print(f"Moved plot to {umap_plot_path}")
        else:
             print(f"Warning: Scanpy plot file not found at {scanpy_saved_path}")
             # Fallback or error handling needed?

        plt.close('all') # Close figures

        self.update_state(state='PROGRESS', meta={'status': 'Saving processed data...'})
        adata.write(processed_adata_path)

        # Clean up temporary figure dir if needed, or leave for debugging
        # Be cautious if multiple tasks run concurrently

        return {'status': 'Complete', 'processed_data_path': str(processed_adata_path), 'umap_plot_path': str(umap_plot_path)}

    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': 'Error during analysis', 'error': str(e)})
        # Re-raise the exception so Celery marks the task as failed
        raise e