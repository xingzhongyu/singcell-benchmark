import scanpy as sc
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

from ..core.config import RESULT_DIR_STR
from celery_app import celery_app

FIGURE_DIR_TEMP = Path(RESULT_DIR_STR) / "temp_figures"
FIGURE_DIR_TEMP.mkdir(parents=True, exist_ok=True)
sc.settings.figdir = str(FIGURE_DIR_TEMP)

@celery_app.task(bind=True, name='app.tasks.trajectory_tasks.run_trajectory_analysis')
def run_trajectory_analysis(self, params: dict):
    """ Celery task for trajectory analysis using Diffmap and PAGA. """
    self.update_state(state='STARTED', meta={'status': 'Starting trajectory analysis...'})

    data_id = params['source_data_id']
    result_data_dir = Path(RESULT_DIR_STR) / data_id
    # Source data can be processed or integrated
    source_adata_path_proc = result_data_dir / f"{data_id}_processed.h5ad"
    source_adata_path_int = result_data_dir / f"{data_id}_integrated.h5ad"

    if source_adata_path_proc.exists():
         source_adata_path = source_adata_path_proc
    elif source_adata_path_int.exists():
         source_adata_path = source_adata_path_int
    else:
         raise FileNotFoundError(f"Source AnnData not found for ID {data_id}")

    # Define output paths within the *source* data ID's result folder
    diffmap_plot_path = result_data_dir / "diffmap.png"
    paga_graph_plot_path = result_data_dir / "paga_graph.png"
    paga_umap_plot_path = result_data_dir / "paga_umap_embedding.png"
    dpt_umap_plot_path = result_data_dir / "umap_dpt_pseudotime.png"
    # Optional: Save updated adata? Or just plots? Let's start with plots.
    # updated_adata_path = result_data_dir / f"{data_id}_trajectory.h5ad"

    results_summary = {'source_data_id': data_id}

    try:
        # 1. Load Data
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...', 'step': 1, 'total_steps': 6})
        adata = sc.read_h5ad(source_adata_path)

        # Ensure neighbors graph exists (required for diffmap/paga)
        if 'neighbors' not in adata.uns:
             raise ValueError("Neighbors graph ('neighbors') not found in AnnData. Run Neighbors calculation first.")

        # 2. Run Diffusion Map
        if params.get('run_diffmap', True):
            self.update_state(state='PROGRESS', meta={'status': 'Running Diffusion Map...', 'step': 2, 'total_steps': 6})
            sc.tl.diffmap(adata, n_comps=params.get('diffmap_n_comps', 15))
            results_summary['diffmap_done'] = True
            try:
                temp_plot_dm = f"diffmap_{data_id}_{uuid.uuid4()}.png"
                sc.pl.diffmap(adata, color=[params.get('paga_clustering_key', 'clusters')], # Color by clusters
                              save=f"_{temp_plot_dm}", show=False)
                scanpy_dm_path = FIGURE_DIR_TEMP / f"diffmap_{temp_plot_dm}"
                if scanpy_dm_path.exists():
                     scanpy_dm_path.rename(diffmap_plot_path)
                     results_summary['diffmap_plot_path'] = str(diffmap_plot_path)
                plt.close('all')
            except Exception as plot_err:
                 print(f"Warning: Could not generate diffmap plot: {plot_err}")

        # 3. Run PAGA
        if params.get('run_paga', True):
             cluster_key = params.get('paga_clustering_key', 'clusters')
             if cluster_key not in adata.obs:
                  raise ValueError(f"PAGA clustering key '{cluster_key}' not found in adata.obs.")
             self.update_state(state='PROGRESS', meta={'status': 'Running PAGA...', 'step': 3, 'total_steps': 6})
             sc.tl.paga(adata, groups=cluster_key,
                        # Use connectivities threshold? Check scanpy docs/best practice
                        # threshold_connectivities=params.get('paga_threshold_connectivities', 0.05)
                       )
             results_summary['paga_done'] = True

             # Plot PAGA graph
             try:
                temp_plot_paga_g = f"paga_graph_{data_id}_{uuid.uuid4()}.png"
                sc.pl.paga(adata, threshold=params.get('paga_threshold_confidence', 0.01), # Threshold for plotting edges
                           save=f"_graph_{temp_plot_paga_g}", show=False)
                scanpy_paga_g_path = FIGURE_DIR_TEMP / f"paga_graph_{temp_plot_paga_g}"
                if scanpy_paga_g_path.exists():
                    scanpy_paga_g_path.rename(paga_graph_plot_path)
                    results_summary['paga_graph_plot_path'] = str(paga_graph_plot_path)
                plt.close('all')
             except Exception as plot_err:
                 print(f"Warning: Could not generate PAGA graph plot: {plot_err}")

             # Plot PAGA on UMAP embedding
             if 'X_umap' in adata.obsm:
                 try:
                    temp_plot_paga_u = f"paga_umap_{data_id}_{uuid.uuid4()}.png"
                    sc.pl.paga(adata, threshold=params.get('paga_threshold_confidence', 0.01),
                               layout='umap', # Plot on existing UMAP
                               save=f"_umap_{temp_plot_paga_u}", show=False)
                    scanpy_paga_u_path = FIGURE_DIR_TEMP / f"paga_umap_{temp_plot_paga_u}"
                    if scanpy_paga_u_path.exists():
                         scanpy_paga_u_path.rename(paga_umap_plot_path)
                         results_summary['paga_umap_plot_path'] = str(paga_umap_plot_path)
                    plt.close('all')
                 except Exception as plot_err:
                     print(f"Warning: Could not generate PAGA UMAP plot: {plot_err}")
             else:
                  print("Info: UMAP embedding not found, skipping PAGA UMAP plot.")


        # 4. Calculate DPT (Diffusion Pseudotime)
        root_cluster = params.get('dpt_root_cluster')
        if params.get('calculate_dpt', True) and root_cluster:
             self.update_state(state='PROGRESS', meta={'status': 'Calculating DPT...', 'step': 4, 'total_steps': 6})
             cluster_key = params.get('paga_clustering_key', 'clusters')
             if cluster_key not in adata.obs:
                  raise ValueError(f"DPT clustering key '{cluster_key}' not found in adata.obs.")

             # Find a cell index within the root cluster
             root_indices = np.where(adata.obs[cluster_key] == root_cluster)[0]
             if len(root_indices) == 0:
                  raise ValueError(f"Root cluster '{root_cluster}' not found in '{cluster_key}' column.")
             # Use the first cell of the root cluster as the root index for DPT
             adata.uns['iroot'] = root_indices[0]
             results_summary['dpt_root_index_used'] = int(adata.uns['iroot']) # Store which cell index was used

             sc.tl.dpt(adata)
             results_summary['dpt_calculated'] = True

             # 5. Plot DPT on UMAP
             if 'X_umap' in adata.obsm:
                  self.update_state(state='PROGRESS', meta={'status': 'Plotting DPT on UMAP...', 'step': 5, 'total_steps': 6})
                  try:
                     temp_plot_dpt_u = f"umap_dpt_{data_id}_{uuid.uuid4()}.png"
                     sc.pl.umap(adata, color=['dpt_pseudotime'], cmap='viridis',
                                save=f"_dpt_{temp_plot_dpt_u}", show=False)
                     scanpy_dpt_u_path = FIGURE_DIR_TEMP / f"umap_dpt_{temp_plot_dpt_u}"
                     if scanpy_dpt_u_path.exists():
                          scanpy_dpt_u_path.rename(dpt_umap_plot_path)
                          results_summary['dpt_umap_plot_path'] = str(dpt_umap_plot_path)
                     plt.close('all')
                  except Exception as plot_err:
                       print(f"Warning: Could not generate DPT UMAP plot: {plot_err}")
             else:
                  print("Info: UMAP embedding not found, skipping DPT UMAP plot.")

        # 6. Save Updated Data (Optional)
        self.update_state(state='PROGRESS', meta={'status': 'Finalizing...', 'step': 6, 'total_steps': 6})
        # If you want to save the adata with trajectory results:
        # adata.write(updated_adata_path, compression='gzip')
        # results_summary['updated_adata_path'] = str(updated_adata_path)

        return {'status': 'Complete', 'results_summary': results_summary}

    except Exception as e:
        import traceback
        self.update_state(state='FAILURE', meta={'status': 'Error during trajectory analysis', 'error': str(e), 'traceback': traceback.format_exc()})
        raise e
    finally:
        plt.close('all')
        # Clean up temp files if needed