# backend/app/tasks/scanpy_tasks.py
import scanpy as sc
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from ..core.config import UPLOAD_DIR_STR, RESULT_DIR_STR
from celery_app import celery_app

# Define base directory for figures if needed, relative to RESULT_DIR
FIGURE_DIR_TEMP = Path(RESULT_DIR_STR) / "temp_figures"
FIGURE_DIR_TEMP.mkdir(parents=True, exist_ok=True)
sc.settings.figdir = str(FIGURE_DIR_TEMP) # Tell Scanpy where to save temporary figures
sc.settings.verbosity = 3 # Default: 3 (info)
# Adjust figure aesthetics if desired
# sc.settings.set_figure_params(dpi=80, facecolor='white')


@celery_app.task(bind=True, name='app.tasks.scanpy_tasks.run_scanpy_analysis')
def run_scanpy_analysis(self, data_id: str, params: dict):
    """
    Celery task to perform expanded Scanpy analysis based on params.
    """
    adata_path = os.path.join(UPLOAD_DIR_STR, f"{data_id}.h5ad")
    result_data_dir = Path(RESULT_DIR_STR) / data_id
    result_data_dir.mkdir(parents=True, exist_ok=True)

    # Define output file paths
    processed_adata_path = result_data_dir / f"{data_id}_processed.h5ad"
    qc_violin_path = result_data_dir / "qc_violin_before_filter.png"
    umap_plot_path = result_data_dir / f"umap_{params['clustering_method']}.png" # Include method in name
    marker_genes_path = result_data_dir / f"marker_genes_{params['clustering_method']}.csv"

    results_summary = {} # To store paths and info

    try:
        # --- 1. Load Data ---
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...', 'step': 1, 'total_steps': 10})
        adata = sc.read_h5ad(adata_path)
        adata.var_names_make_unique() # Ensure unique gene names
        results_summary['original_shape'] = {'obs': adata.n_obs, 'var': adata.n_vars}

        # --- 2. Calculate QC Metrics ---
        self.update_state(state='PROGRESS', meta={'status': 'Calculating QC metrics...', 'step': 2, 'total_steps': 10})
        mito_prefix = params.get('mito_prefix', 'MT-') # Use provided prefix
        adata.var['mito'] = adata.var_names.str.startswith(mito_prefix)
        sc.pp.calculate_qc_metrics(adata, qc_vars=['mito'], percent_top=None, log1p=False, inplace=True)
        results_summary['qc_calculated'] = True

        # --- 3. Plot QC Violin (Before Filtering) ---
        self.update_state(state='PROGRESS', meta={'status': 'Generating QC plot...', 'step': 3, 'total_steps': 10})
        try:
            # Use a unique temp filename
            temp_qc_filename = f"qc_violin_{data_id}_{uuid.uuid4()}.png"
            sc.pl.violin(
                adata,
                ['n_genes_by_counts', 'total_counts', 'pct_counts_mito'],
                jitter=0.4, multi_panel=True, show=False, save=f"_{temp_qc_filename}"
            )
            scanpy_qc_path = FIGURE_DIR_TEMP / f"violin_{temp_qc_filename}"
            if scanpy_qc_path.exists():
                scanpy_qc_path.rename(qc_violin_path)
                results_summary['qc_plot_path'] = str(qc_violin_path)
            else:
                 print(f"Warning: Scanpy QC plot file not found at {scanpy_qc_path}")
            plt.close('all')
        except Exception as plot_err:
            print(f"Warning: Could not generate QC plot: {plot_err}")
            results_summary['qc_plot_path'] = None # Indicate plot failed


        # --- 4. Basic Filtering ---
        self.update_state(state='PROGRESS', meta={'status': 'Applying basic filters...', 'step': 4, 'total_steps': 10})
        sc.pp.filter_cells(adata, min_genes=params.get('min_genes_after_qc', 200))
        sc.pp.filter_genes(adata, min_cells=params.get('min_cells_after_qc', 3))
        results_summary['shape_after_basic_filter'] = {'obs': adata.n_obs, 'var': adata.n_vars}

        # --- (Optional) Advanced QC Filtering ---
        # Example: Filtering based on max % mito (add params if needed)
        # max_pct_mito = params.get('qc_max_pct_mito')
        # if max_pct_mito is not None:
        #     self.update_state(state='PROGRESS', meta={'status': f'Filtering cells by max {max_pct_mito}% mito...', 'step': 4.5, 'total_steps': 10})
        #     adata = adata[adata.obs.pct_counts_mito < max_pct_mito, :]
        #     results_summary['shape_after_mito_filter'] = {'obs': adata.n_obs, 'var': adata.n_vars}

        # --- 5. Normalization & Logarithmize ---
        self.update_state(state='PROGRESS', meta={'status': 'Normalizing and Logarithmizing...', 'step': 5, 'total_steps': 10})
        target_sum = params.get('normalize_target_sum')
        if target_sum is not None and target_sum > 0:
             sc.pp.normalize_total(adata, target_sum=target_sum)
             sc.pp.log1p(adata)
             results_summary['normalized'] = True
        else:
             results_summary['normalized'] = False # Skipped


        # --- 6. Highly Variable Genes (Optional) ---
        if params.get('select_hvgs', True):
            self.update_state(state='PROGRESS', meta={'status': 'Finding Highly Variable Genes...', 'step': 6, 'total_steps': 10})
            n_top = params.get('hvg_n_top_genes')
            if n_top is not None and n_top > 0:
                 sc.pp.highly_variable_genes(adata, n_top_genes=n_top)
            else:
                 sc.pp.highly_variable_genes(adata, min_mean=params.get('hvg_min_mean', 0.0125),
                                            max_mean=params.get('hvg_max_mean', 3),
                                            min_disp=params.get('hvg_min_disp', 0.5))
            results_summary['hvg_calculated'] = True
            adata = adata[:, adata.var.highly_variable].copy() # Subset to HVGs
            results_summary['shape_after_hvg'] = {'obs': adata.n_obs, 'var': adata.n_vars}
        else:
            results_summary['hvg_calculated'] = False # Skipped


        # --- (Optional) Scaling ---
        # Often applied if HVGs were selected
        # if params.get('select_hvgs', True):
        #     self.update_state(state='PROGRESS', meta={'status': 'Scaling data...', 'step': 6.5, 'total_steps': 10})
        #     sc.pp.scale(adata, max_value=params.get('scale_max_value', 10))
        #     results_summary['scaled'] = True

        # --- 7. PCA ---
        self.update_state(state='PROGRESS', meta={'status': 'Running PCA...', 'step': 7, 'total_steps': 10})
        n_comps = min(params.get('pca_n_comps', 50), adata.n_obs - 1, adata.n_vars - 1) # Ensure n_comps is valid
        if n_comps < 2 :
             raise ValueError(f"Too few features/observations ({adata.n_vars}/{adata.n_obs}) to run PCA with n_comps={n_comps}. Need at least 2.")
        sc.tl.pca(adata, svd_solver='arpack', n_comps=n_comps)
        results_summary['pca_done'] = True


        # --- 8. Neighbors ---
        self.update_state(state='PROGRESS', meta={'status': 'Calculating Neighbors...', 'step': 8, 'total_steps': 10})
        n_pcs_neighbors = min(params.get('neighbors_n_pcs', 30), n_comps) # Use fewer PCs, ensure <= total PCs
        sc.pp.neighbors(adata, n_neighbors=params.get('neighbors_n_neighbors', 15), n_pcs=n_pcs_neighbors)
        results_summary['neighbors_done'] = True


        # --- 9. UMAP ---
        self.update_state(state='PROGRESS', meta={'status': 'Running UMAP...', 'step': 9, 'total_steps': 10})
        sc.tl.umap(adata, min_dist=params.get('umap_min_dist', 0.5), spread=params.get('umap_spread', 1.0))
        results_summary['umap_done'] = True


        # --- 10. Clustering (Leiden or Louvain) ---
        clustering_method = params.get('clustering_method', 'leiden')
        self.update_state(state='PROGRESS', meta={'status': f'Running {clustering_method.capitalize()} Clustering...', 'step': 10, 'total_steps': 11}) # Adjusted total steps
        if clustering_method == 'leiden':
            resolution = params.get('leiden_resolution', 0.5)
            sc.tl.leiden(adata, resolution=resolution, key_added='clusters') # Use consistent key 'clusters'
        elif clustering_method == 'louvain':
            resolution = params.get('louvain_resolution', 0.5)
            sc.tl.louvain(adata, resolution=resolution, key_added='clusters') # Use consistent key 'clusters'
        else:
            raise ValueError(f"Unsupported clustering method: {clustering_method}")
        adata.obs['clusters'] = adata.obs['clusters'].astype('category') # Ensure categorical for plotting/ranking
        results_summary['clustering_done'] = {'method': clustering_method, 'resolution': resolution}


        # --- 11. Marker Gene Detection ---
        self.update_state(state='PROGRESS', meta={'status': 'Finding Marker Genes...', 'step': 11, 'total_steps': 11}) # Last step
        marker_method = params.get('marker_gene_method', 'wilcoxon')
        n_markers = params.get('marker_gene_n_genes', 25)
        sc.tl.rank_genes_groups(adata, 'clusters', method=marker_method, n_genes=n_markers, key_added='rank_genes_clusters')
        results_summary['marker_genes_calculated'] = True

        # Extract and save marker genes to CSV
        try:
            marker_results = sc.get.rank_genes_groups_df(adata, group=None, key='rank_genes_clusters') # Get all groups
            marker_results.to_csv(marker_genes_path, index=False)
            results_summary['marker_genes_path'] = str(marker_genes_path)
        except Exception as marker_err:
            print(f"Warning: Could not save marker genes: {marker_err}")
            results_summary['marker_genes_path'] = None

        # --- Generate and Save UMAP Plot (colored by clusters) ---
        self.update_state(state='PROGRESS', meta={'status': 'Generating UMAP plot...', 'step': 11, 'total_steps': 11}) # Part of last step
        try:
            # Use a unique temp filename including cluster method
            temp_plot_filename = f"umap_{clustering_method}_{data_id}_{uuid.uuid4()}.png"
            sc.pl.umap(adata, color=['clusters'], save=f"_{temp_plot_filename}", show=False,
                       title=f"{clustering_method.capitalize()} (res={resolution})",
                       legend_loc='on data' if len(adata.obs['clusters'].cat.categories) <= 10 else 'right margin') # Adjust legend

            scanpy_saved_path = FIGURE_DIR_TEMP / f"umap_{temp_plot_filename}"
            if scanpy_saved_path.exists():
                scanpy_saved_path.rename(umap_plot_path)
                results_summary['umap_plot_path'] = str(umap_plot_path)
                print(f"Moved plot to {umap_plot_path}")
            else:
                 print(f"Warning: Scanpy UMAP plot file not found at {scanpy_saved_path}")
                 results_summary['umap_plot_path'] = None
            plt.close('all')
        except Exception as plot_err:
             print(f"Warning: Could not generate UMAP plot: {plot_err}")
             results_summary['umap_plot_path'] = None


        # --- Final: Save Processed Data ---
        self.update_state(state='PROGRESS', meta={'status': 'Saving processed data...', 'step': 11, 'total_steps': 11})
        # Ensure necessary results are stored for frontend use if needed later
        # Example: Add UMAP coords directly to obs for easier access if needed for gene plots
        # adata.obs['UMAP_1'] = adata.obsm['X_umap'][:, 0]
        # adata.obs['UMAP_2'] = adata.obsm['X_umap'][:, 1]
        adata.write(processed_adata_path, compression='gzip') # Add compression
        results_summary['processed_data_path'] = str(processed_adata_path)

         # --- Ensure ALL paths are strings ---
        final_summary = {}
        for key, value in results_summary.items():
            if isinstance(value, Path):
                final_summary[key] = str(value)
            # Handle nested dicts containing paths (like clustering_done) - though not needed for current structure
            # elif isinstance(value, dict):
            #    final_summary[key] = {k: str(v) if isinstance(v, Path) else v for k, v in value.items()}
            else:
                final_summary[key] = value

        import json # Test serialization explicitly
        json.dumps(final_summary) # This will raise TypeError if not serializable

        print("---------------------------------------------")
        print(f"TASK {self.request.id}: Attempting to return SUCCESS.")
        print(f"Final Serializable Summary: {final_summary}")
        print("---------------------------------------------")
        # --- Return summary of results ---
        return {'status': 'Complete', 'results_summary': final_summary}

    except Exception as final_err:
        # Log any error happening during final prep/serialization
        import traceback
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"TASK {self.request.id}: ERROR during final return preparation: {final_err}")
        print(traceback.format_exc())
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        # Explicitly update state to FAILURE here if needed, though Celery should catch the re-raise
        self.update_state(state='FAILURE', meta={'status': 'Error during final return', 'error': str(final_err), 'traceback': traceback.format_exc()})
        raise final_err # Re-raise so Celery knows it failed
    finally:
       # Clean up temporary figure directory contents
        print(f"TASK {self.request.id}: Entering finally block.")
        try:
            items_to_remove = list(FIGURE_DIR_TEMP.glob(f"*{data_id}*")) # Find items related to this task
            print(f"TASK {self.request.id}: Found {len(items_to_remove)} temp items to remove.")
            for item in items_to_remove:
                if item.is_file():
                    try:
                        item.unlink()
                        print(f"TASK {self.request.id}: Removed temp file {item.name}")
                    except OSError as unlink_err:
                        print(f"TASK {self.request.id}: WARNING - Failed to remove temp file {item.name}: {unlink_err}")
                # Add handling for directories if needed
        except Exception as cleanup_err:
            # Catch broader errors during the cleanup search/iteration
            print(f"TASK {self.request.id}: WARNING - Error during figure cleanup process: {cleanup_err}")

        try:
            plt.close('all') # Ensure all plots are closed
            print(f"TASK {self.request.id}: Closed matplotlib figures.")
        except Exception as plt_err:
            print(f"TASK {self.request.id}: WARNING - Error closing matplotlib figures: {plt_err}")
        print(f"TASK {self.request.id}: Exiting finally block.")