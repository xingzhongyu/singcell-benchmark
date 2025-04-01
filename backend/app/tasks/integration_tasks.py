import scanpy as sc
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path

from ..core.config import UPLOAD_DIR_STR, RESULT_DIR_STR,UPLOAD_DIR
from celery_app import celery_app

# Configure temporary figure saving
FIGURE_DIR_TEMP = Path(RESULT_DIR_STR) / "temp_figures"
FIGURE_DIR_TEMP.mkdir(parents=True, exist_ok=True)
sc.settings.figdir = str(FIGURE_DIR_TEMP)

@celery_app.task(bind=True, name='app.tasks.integration_tasks.run_integration')
def run_integration(self, output_data_id: str, params: dict):
    """ Celery task for data integration using BBKNN or Harmony. """
    self.update_state(state='STARTED', meta={'status': 'Starting integration...'})

    files_info = params['files']
    method = params['integration_method']
    batch_key = params.get(f"{method}_batch_key", 'batch') # Get method-specific batch key

    result_data_dir = Path(RESULT_DIR_STR) / output_data_id
    result_data_dir.mkdir(parents=True, exist_ok=True)
    integrated_adata_path = UPLOAD_DIR/ f"{output_data_id}.h5ad"
    umap_batch_plot_path = result_data_dir / "umap_integrated_batch.png"
    umap_clusters_plot_path = result_data_dir / "umap_integrated_clusters.png" # If clusters are computed

    results_summary = {'integrated_data_id': output_data_id}

    try:
        # 1. Load and Concatenate Data
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...', 'step': 1, 'total_steps': 5})
        adatas = []
        for i, f_info in enumerate(files_info):
             adata_path = os.path.join(UPLOAD_DIR_STR, f"{f_info['data_id']}.h5ad")
             adata = sc.read_h5ad(adata_path)
             adata.obs[batch_key] = f_info['batch_label']
             # Ensure var names are unique across datasets before concat? Risky. Assume user pre-aligned.
             # Basic check: ensure some common genes exist?
             adata.var_names_make_unique() # Make unique within dataset at least
             adatas.append(adata)
             self.update_state(state='PROGRESS', meta={'status': f"Loaded {f_info['batch_label']} ({i+1}/{len(files_info)})"})

        # Use outer join, requires genes to be reasonably consistent
        adata_concat = ad.concat(adatas, join='outer', label='input_dataset', index_unique=None) # index_unique handles cell name clashes
        adata_concat.obs[batch_key] = adata_concat.obs[batch_key].astype('category')
        results_summary['concatenated_shape'] = {'obs': adata_concat.n_obs, 'var': adata_concat.n_vars}
        del adatas # Free memory

        # --- Preprocessing before integration (Optional but often needed) ---
        # Example: Highly variable genes on the concatenated object *before* integration
        self.update_state(state='PROGRESS', meta={'status': 'Preprocessing for integration...', 'step': 2, 'total_steps': 5})
        # sc.pp.highly_variable_genes(adata_concat, n_top_genes=2000, subset=True, batch_key=batch_key) # Example HVG selection
        # sc.pp.normalize_total(adata_concat, target_sum=1e4)
        # sc.pp.log1p(adata_concat)
        # Run PCA *before* integration if needed (esp. for Harmony)
        if method == 'harmony' or params.get('run_pca'):
            sc.pp.pca(adata_concat, n_comps=params.get('pca_n_comps', 50))
            results_summary['pca_on_concatenated'] = True


        # 2. Run Integration
        self.update_state(state='PROGRESS', meta={'status': f'Running {method.upper()}...', 'step': 3, 'total_steps': 5})
        if method == 'bbknn':
            # BBKNN modifies the neighbor graph directly
            sc.external.pp.bbknn(
                adata_concat,
                batch_key=batch_key,
                neighbors_within_batch=params.get('bbknn_neighbors_within_batch', 3),
                # n_pcs=params.get('pca_n_comps', 50) # BBKNN uses PCA by default if present
            )
            results_summary['integration_method'] = 'bbknn'
            # Neighbors are calculated by BBKNN
            results_summary['neighbors_done'] = True

        elif method == 'harmony':
            # Harmony creates a corrected embedding in obsm
            sc.external.pp.harmony_integrate(
                adata_concat,
                key=batch_key,
                basis='X_pca', # Requires PCA computed beforehand
                adjusted_basis='X_pca_harmony', # Output key
                theta=params.get('harmony_theta', 2.0),
                max_iter_harmony=params.get('harmony_max_iter_harmony', 10)
            )
            results_summary['integration_method'] = 'harmony'
            # Need to run neighbors on the Harmony embedding
            if params.get('run_neighbors', True):
                 sc.pp.neighbors(adata_concat, n_pcs=params.get('neighbors_n_pcs', 30), use_rep='X_pca_harmony', n_neighbors=params.get('neighbors_n_neighbors', 15))
                 results_summary['neighbors_done'] = True

        else:
            raise ValueError(f"Unsupported integration method: {method}")

        # 3. Run UMAP (on integrated result)
        if params.get('run_umap', True):
             self.update_state(state='PROGRESS', meta={'status': 'Running UMAP on integrated data...', 'step': 4, 'total_steps': 5})
             # UMAP uses the graph computed by BBKNN or on Harmony embedding
             sc.tl.umap(adata_concat, min_dist=params.get('umap_min_dist', 0.5), spread=params.get('umap_spread', 1.0))
             results_summary['umap_done'] = True

             # Plot UMAP colored by batch
             try:
                temp_plot_batch = f"umap_integrated_batch_{output_data_id}_{uuid.uuid4()}.png"
                sc.pl.umap(adata_concat, color=[batch_key], save=f"_{temp_plot_batch}", show=False, title="Integrated UMAP (colored by batch)")
                scanpy_batch_path = FIGURE_DIR_TEMP / f"umap_{temp_plot_batch}"
                if scanpy_batch_path.exists():
                    scanpy_batch_path.rename(umap_batch_plot_path)
                    results_summary['umap_batch_plot_path'] = str(umap_batch_plot_path)
                plt.close('all')
             except Exception as plot_err:
                print(f"Warning: Could not generate integrated batch UMAP plot: {plot_err}")


             # Optional: Run clustering on integrated data and plot
             # sc.tl.leiden(adata_concat, key_added='clusters_integrated')
             # results_summary['clustering_done'] = True
             # try:
             #    temp_plot_clust = f"umap_integrated_clusters_{output_data_id}_{uuid.uuid4()}.png"
             #    sc.pl.umap(adata_concat, color=['clusters_integrated'], save=f"_{temp_plot_clust}", show=False, title="Integrated UMAP (colored by clusters)")
             #    scanpy_clust_path = FIGURE_DIR_TEMP / f"umap_{temp_plot_clust}"
             #    if scanpy_clust_path.exists():
             #       scanpy_clust_path.rename(umap_clusters_plot_path)
             #       results_summary['umap_clusters_plot_path'] = str(umap_clusters_plot_path)
             #    plt.close('all')
             # except Exception as plot_err:
             #    print(f"Warning: Could not generate integrated cluster UMAP plot: {plot_err}")


        # 4. Save Integrated Data
        self.update_state(state='PROGRESS', meta={'status': 'Saving integrated data...', 'step': 5, 'total_steps': 5})
        adata_concat.write(integrated_adata_path, compression='gzip')
        results_summary['integrated_data_path'] = str(integrated_adata_path)

        return {'status': 'Complete', 'results_summary': results_summary}

    except Exception as e:
        import traceback
        self.update_state(state='FAILURE', meta={'status': 'Error during integration', 'error': str(e), 'traceback': traceback.format_exc()})
        raise e
    finally:
         plt.close('all')
         # Clean up temp files if needed