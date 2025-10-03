# backend/app/tasks/atac_tasks.py
import muon as mu
import mudata as md # MuData objects
import scanpy as sc # Muon uses scanpy functions
import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path
import traceback

# Import muon's ATAC module
try:
    import muon.atac as muatac
except ImportError:
    print("ERROR: Muon ATAC module (muon.atac) not found or import failed. Install with 'pip install muon[atac]'.")
    muatac = None # Handle gracefully

from ..core.config import UPLOAD_DIR_STR, RESULT_DIR_STR
from celery_app import celery_app

# Configure temporary figure saving using scanpy's settings
FIGURE_DIR_TEMP = Path(RESULT_DIR_STR) / "temp_figures"
FIGURE_DIR_TEMP.mkdir(parents=True, exist_ok=True)
sc.settings.figdir = str(FIGURE_DIR_TEMP)
sc.settings.verbosity = 3

@celery_app.task(bind=True, name='app.tasks.atac_tasks.run_atac_analysis')
def run_atac_analysis(self, params: dict):
    """ Celery task to run ATAC-seq analysis using Muon. """
    if muatac is None:
        raise ImportError("Muon ATAC module failed to import. Cannot run analysis.")

    self.update_state(state='STARTED', meta={'status': 'Starting ATAC analysis...'})

    data_id = params['source_data_id']
    adata_path = Path(UPLOAD_DIR_STR) / f"{data_id}.h5ad"
    if not adata_path.exists():
        raise FileNotFoundError(f"Source ATAC AnnData file not found at {adata_path}.")

    result_data_dir = Path(RESULT_DIR_STR) / data_id
    result_data_dir.mkdir(parents=True, exist_ok=True) # Ensure result dir exists

    # Define output paths
    processed_adata_path = result_data_dir / f"{data_id}_processed_atac.h5ad"
    qc_plot_path = result_data_dir / "atac_qc_violin.png"
    umap_plot_path_base = result_data_dir / "atac_umap" # Base name for UMAP plots

    results_summary = {'source_data_id': data_id}
    mdata = None # Use MuData object internally, even for single modality

    try:
        # 1. Load ATAC data into a MuData object
        self.update_state(state='PROGRESS', meta={'status': 'Loading ATAC data...', 'step': 1, 'total_steps': 8})
        adata_atac = sc.read_h5ad(adata_path)
        # Ensure feature names are strings if needed by downstream tools
        adata_atac.var_names = adata_atac.var_names.astype(str)
        mdata = md.MuData({'atac': adata_atac}) # Wrap in MuData
        results_summary['data_loaded'] = True
        results_summary['initial_shape'] = {'obs': mdata.n_obs, 'var': mdata.n_vars}

        # --- Access the ATAC modality ---
        atac = mdata.mod['atac']

        # 2. Basic QC Calculation (Muon)
        # Note: TSS/FRiP calculations often require external files/annotations not handled here yet.
        self.update_state(state='PROGRESS', meta={'status': 'Calculating ATAC QC metrics...', 'step': 2, 'total_steps': 8})
        # muatac.pp.calulate_qc_metrics will add obs columns like 'total_counts', 'n_features_by_counts'
        try:
             # Using scanpy's QC function as muon's might be deprecated or less direct for simple metrics
             sc.pp.calculate_qc_metrics(atac, percent_top=None, log1p=False, inplace=True)
             results_summary['qc_calculated'] = True

             # Plot QC Violin (Before Filtering)
             qc_vars = ['total_counts', 'n_features_by_counts']
             # Add TSS/FRiP if calculated: e.g., ['total_counts', ..., 'tss_enrichment', 'fract_reads_in_peaks']
             temp_qc_filename = f"atac_qc_violin_{data_id}_{uuid.uuid4()}.png"
             sc.pl.violin(atac, qc_vars, jitter=0.4, multi_panel=True, show=False, save=f"_{temp_qc_filename}")
             scanpy_qc_path = FIGURE_DIR_TEMP / f"violin_{temp_qc_filename}"
             if scanpy_qc_path.exists():
                 scanpy_qc_path.rename(qc_plot_path)
                 results_summary['qc_plot_path'] = str(qc_plot_path)
             else: print(f"Warning: ATAC QC plot file not found at {scanpy_qc_path}")
             plt.close('all')

        except Exception as qc_err:
             print(f"Warning: Failed during QC calculation or plotting: {qc_err}\n{traceback.format_exc()}")
             results_summary['qc_calculated'] = False
             results_summary['qc_plot_path'] = None


        # 3. Filtering based on QC
        self.update_state(state='PROGRESS', meta={'status': 'Filtering cells/features...', 'step': 3, 'total_steps': 8})
        try:
             # Muon provides muon.pp.filter_obs / filter_var which operate on MuData
             # Filter cells
             mu.pp.filter_obs(mdata, 'total_counts', lambda x: x >= params.get('qc_min_counts', 1000))
             # Filter by max counts quantile (more robust than absolute max)
             max_counts_threshold = atac.obs['total_counts'].quantile(params.get('qc_max_counts_quantile', 0.99))
             mu.pp.filter_obs(mdata, 'total_counts', lambda x: x <= max_counts_threshold)
             mu.pp.filter_obs(mdata, 'n_features_by_counts', lambda x: x >= params.get('qc_min_features_by_counts', 500))
             # Add TSS/FRiP filters here if metrics are available and params are set

             # Filter features (e.g., keep features present in at least N cells) - Optional
             # mu.pp.filter_var(mdata, 'n_cells_by_counts', lambda x: x >= 10) # Keep features in >= 10 cells

             results_summary['shape_after_filtering'] = {'obs': mdata.n_obs, 'var': mdata.n_vars}
             print(f"Shape after filtering: {mdata.n_obs} cells, {mdata.n_vars} features")
        except Exception as filter_err:
             print(f"Warning: Error during filtering: {filter_err}. Proceeding with unfiltered data if possible.")
             # Decide how to handle - stop task or continue? Continuing might lead to poor results.
             # raise filter_err # Option to stop the task

        # Refresh atac variable after filtering
        atac = mdata.mod['atac']

        # 4. TF-IDF Transformation (Common for ATAC)
        if params.get('tfidf_transform', True):
            self.update_state(state='PROGRESS', meta={'status': 'Applying TF-IDF...', 'step': 4, 'total_steps': 8})
            # Use muon.atac.pp.tfidf or scanpy's tfidf
            try:
                 # scanpy's tfidf is often used and works on AnnData
                 sc.pp.tfidf(atac, scale_factor=params.get('tfidf_scale_factor')) # scale_factor is optional
                 results_summary['tfidf_done'] = True
                 print("TF-IDF transformation applied.")
            except Exception as tfidf_err:
                 print(f"Warning: TF-IDF failed: {tfidf_err}. Skipping.")
                 results_summary['tfidf_done'] = False
        else:
             results_summary['tfidf_done'] = False
             print("Skipping TF-IDF transformation.")


        # 5. Dimensionality Reduction (LSI/SVD)
        # Note: Muon might have muatac.tl.lsi, check its implementation. Scanpy's SVD on TF-IDF is common.
        self.update_state(state='PROGRESS', meta={'status': 'Running LSI (SVD)...', 'step': 5, 'total_steps': 8})
        try:
             # Ensure data is in CSR format for SVD performance if large
             # if not isinstance(atac.X, sparse.csr_matrix): atac.X = sparse.csr_matrix(atac.X)

             # Use scanpy's pca function which performs SVD on sparse data (suitable for LSI)
             # n_comps should be +1 because the first component is often related to library size/depth and removed
             n_svd_comps = params.get('lsi_n_components', 50) + 1
             sc.tl.pca(atac, n_comps=n_svd_comps, svd_solver='arpack', use_highly_variable=params.get('lsi_use_highly_variable', False))
             # The result is in atac.obsm['X_pca'] and atac.varm['PCs']

             # Store LSI results, excluding the first component
             # Muon convention is often 'X_lsi'
             atac.obsm['X_lsi'] = atac.obsm['X_pca'][:, 1:]
             # Store loadings if needed, excluding first component
             # atac.varm['LSI'] = atac.varm['PCs'][:, 1:]

             results_summary['lsi_done'] = {'n_components_used': n_svd_comps - 1}
             print(f"LSI (SVD) completed. Using components 1 to {n_svd_comps -1}.")
        except Exception as lsi_err:
             print(f"ERROR: LSI failed: {lsi_err}\n{traceback.format_exc()}")
             raise lsi_err # Stop the task if LSI fails, as downstream steps depend on it


        # 6. Neighbors Graph (using LSI components)
        self.update_state(state='PROGRESS', meta={'status': 'Calculating Neighbors on LSI...', 'step': 6, 'total_steps': 8})
        try:
             n_lsi_neighbors = min(params.get('neighbors_n_pcs', 30), atac.obsm['X_lsi'].shape[1]) # Ensure valid number of components
             sc.pp.neighbors(
                 atac,
                 n_neighbors=params.get('neighbors_n_neighbors', 15),
                 n_pcs=n_lsi_neighbors,
                 use_rep='X_lsi', # Use the LSI embedding
                 metric='cosine' # Cosine distance is common for LSI
             )
             results_summary['neighbors_done'] = True
             print("Neighbors graph calculated on LSI components.")
        except Exception as neighbor_err:
              print(f"ERROR: Neighbors calculation failed: {neighbor_err}\n{traceback.format_exc()}")
              raise neighbor_err # Stop task


        # 7. UMAP & Clustering
        if params.get('run_umap', True):
            self.update_state(state='PROGRESS', meta={'status': 'Running UMAP...', 'step': 7, 'total_steps': 8})
            try:
                 sc.tl.umap(
                     atac,
                     min_dist=params.get('umap_min_dist', 0.5),
                     spread=params.get('umap_spread', 1.0)
                     # UMAP runs on the neighbors graph computed in the previous step
                 )
                 results_summary['umap_done'] = True
                 print("UMAP calculation completed.")
            except Exception as umap_err:
                  print(f"Warning: UMAP failed: {umap_err}. Skipping UMAP plot generation.")
                  results_summary['umap_done'] = False

        if params.get('run_clustering', True):
             self.update_state(state='PROGRESS', meta={'status': 'Running Leiden Clustering...', 'step': 7.5, 'total_steps': 8}) # Combine step
             try:
                sc.tl.leiden(
                    atac,
                    resolution=params.get('clustering_resolution', 0.5),
                    key_added='clusters' # Standard key
                )
                results_summary['clustering_done'] = True
                print("Leiden clustering completed.")

                # Plot UMAP colored by clusters if both ran
                if results_summary.get('umap_done'):
                     try:
                         umap_cluster_plot_path = result_data_dir / f"{umap_plot_path_base.name}_clusters.png"
                         temp_umap_c_file = f"{umap_plot_path_base.name}_clusters_{data_id}_{uuid.uuid4()}.png"
                         sc.pl.umap(atac, color=['clusters'], save=f"_{temp_umap_c_file}", show=False, title="ATAC UMAP (Clusters)")
                         scanpy_umap_c_path = FIGURE_DIR_TEMP / f"umap_{temp_umap_c_file}"
                         if scanpy_umap_c_path.exists():
                             scanpy_umap_c_path.rename(umap_cluster_plot_path)
                             results_summary['umap_cluster_plot_path'] = str(umap_cluster_plot_path)
                         else: print(f"Warning: ATAC UMAP cluster plot not found at {scanpy_umap_c_path}")
                         plt.close('all')
                     except Exception as umap_plot_err:
                          print(f"Warning: Failed to plot UMAP by clusters: {umap_plot_err}")

             except Exception as cluster_err:
                 print(f"Warning: Clustering failed: {cluster_err}. Skipping.")
                 results_summary['clustering_done'] = False
        else:
             results_summary['clustering_done'] = False


        # Optional: Add other UMAP plots (e.g., colored by total_counts)


        # 8. Save Processed ATAC AnnData (within MuData context if needed later)
        if params.get('save_processed_adata', True):
             self.update_state(state='PROGRESS', meta={'status': 'Saving processed ATAC data...', 'step': 8, 'total_steps': 8})
             try:
                 # Save only the processed ATAC AnnData
                 atac.write(processed_adata_path, compression="gzip")
                 # Alternatively, save the whole MuData object if it contained more modalities later
                 # mdata.write(result_data_dir / f"{data_id}_processed.h5mu", compression="gzip")
                 results_summary['processed_adata_path'] = str(processed_adata_path)
                 print(f"Saved processed ATAC AnnData to {processed_adata_path}")
             except Exception as write_err:
                  print(f"Warning: Failed to save processed ATAC AnnData: {write_err}")
                  results_summary['processed_adata_path'] = None
        else:
             self.update_state(state='PROGRESS', meta={'status': 'Skipping final save...', 'step': 8, 'total_steps': 8})


        # --- Cleanup MuData ---
        # If mdata is large, explicitly delete it
        del mdata
        del atac

        return {'status': 'Complete', 'results_summary': results_summary}

    except Exception as e:
        # General error handling
        error_traceback = traceback.format_exc()
        print(f"An unexpected error occurred during ATAC analysis: {e}")
        print(error_traceback)
        self.update_state(state='FAILURE', meta={'status': 'Error during ATAC analysis', 'error': str(e), 'traceback': error_traceback})
        # Ensure mdata is cleaned up on error too
        try: del mdata
        except NameError: pass
        try: del atac
        except NameError: pass
        raise e
    finally:
         plt.close('all')
         # Clean up temp figure files if needed