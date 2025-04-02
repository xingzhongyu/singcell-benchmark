# backend/app/tasks/velocity_tasks.py
import scanpy as sc
import scvelo as scv
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path
import traceback

from ..core.config import UPLOAD_DIR_STR, RESULT_DIR_STR
from celery_app import celery_app

# Configure settings for scvelo plotting if needed
# scv.settings.figdir = str(Path(RESULT_DIR_STR) / "temp_figures") # Use Scanpy's temp dir?
scv.settings.verbosity = 3  # Adjust verbosity (0=error, 1=warning, 2=info, 3=hint)
scv.settings.set_figure_params('scvelo') # Use scvelo's default parameters

@celery_app.task(bind=True, name='app.tasks.velocity_tasks.run_rna_velocity')
def run_rna_velocity(self, params: dict):
    """ Celery task to run RNA Velocity analysis using scVelo. """
    self.update_state(state='STARTED', meta={'status': 'Starting RNA Velocity analysis...'})

    data_id = params['source_data_id']
    # --- IMPORTANT: Load the ORIGINAL uploaded file ---
    # Velocity calculation needs the raw spliced/unspliced layers
    adata_original_path = Path(UPLOAD_DIR_STR) / f"{data_id}.h5ad"
    if not adata_original_path.exists():
        raise FileNotFoundError(f"Original AnnData file not found at {adata_original_path}. Cannot run velocity analysis.")

    # We also need a processed AnnData (potentially) for embeddings and neighbor graph
    result_data_dir = Path(RESULT_DIR_STR) / data_id
    result_data_dir.mkdir(parents=True, exist_ok=True) # Ensure result dir exists
    adata_processed_path = result_data_dir / f"{data_id}_processed.h5ad"
    adata_integrated_path = result_data_dir / f"{data_id}_integrated.h5ad"

    # Define output paths (within the *source* data ID's result folder)
    basis = params.get('embedding_basis', 'umap') # Basis used for plotting
    plot_base_name = f"velocity_embedding_{basis}"
    grid_plot_path = result_data_dir / f"{plot_base_name}_grid.png"
    stream_plot_path = result_data_dir / f"{plot_base_name}_stream.png"
    updated_adata_path = result_data_dir / f"{data_id}_velocity.h5ad" # Optional output

    results_summary = {'source_data_id': data_id}
    adata_for_velocity = None # Initialize

    try:
        # 1. Load Original Data
        self.update_state(state='PROGRESS', meta={'status': 'Loading original data with layers...', 'step': 1, 'total_steps': 7})
        adata_orig = sc.read_h5ad(adata_original_path)
        results_summary['original_data_loaded'] = True

        # --- Check for required layers ---
        if 'spliced' not in adata_orig.layers or 'unspliced' not in adata_orig.layers:
            raise ValueError("Required layers 'spliced' and 'unspliced' not found in the original AnnData file.")
        print(f"Found 'spliced' and 'unspliced' layers in {adata_original_path.name}")

        # 2. Merge Original Layers with Processed/Integrated Data
        # We need the embeddings, neighbors graph, and clustering from a processed object
        # overlaid onto the object containing the spliced/unspliced layers.
        self.update_state(state='PROGRESS', meta={'status': 'Loading processed data and merging...', 'step': 2, 'total_steps': 7})
        adata_proc = None
        if adata_processed_path.exists():
            adata_proc = sc.read_h5ad(adata_processed_path)
            print(f"Loading pre-processed data from: {adata_processed_path.name}")
        elif adata_integrated_path.exists():
            adata_proc = sc.read_h5ad(adata_integrated_path)
            print(f"Loading pre-processed data from: {adata_integrated_path.name}")
        else:
            # Velocity can technically run without processed data, but plots will fail.
            print(f"Warning: No processed/integrated AnnData found. Using original data for velocity calculation. Embedding plots will likely fail unless '{basis}' exists in original data.")
            adata_for_velocity = adata_orig.copy() # Work on a copy
            # Basic preprocessing needed if using only original data
            scv.pp.filter_and_normalize(adata_for_velocity, min_shared_counts=params.get('min_shared_counts', 20), n_top_genes=params.get('n_top_genes', 2000))
            scv.pp.moments(adata_for_velocity, n_pcs=30, n_neighbors=30) # Calculate moments

        if adata_proc:
            # --- Careful Merging ---
            # Ensure cell order is the same or subset appropriately
            common_cells = adata_orig.obs_names.intersection(adata_proc.obs_names)
            if len(common_cells) == 0:
                 raise ValueError("No common cells found between original and processed AnnData objects.")
            if len(common_cells) < adata_orig.n_obs or len(common_cells) < adata_proc.n_obs:
                 print(f"Warning: Subsetting to {len(common_cells)} common cells found between original and processed data.")

            adata_orig = adata_orig[common_cells, :].copy()
            adata_proc = adata_proc[common_cells, :].copy()

            # Create the object for velocity analysis: start with original (contains layers)
            adata_for_velocity = adata_orig

            # Copy essential information from processed data
            # Embeddings:
            if f'X_{basis}' in adata_proc.obsm:
                 adata_for_velocity.obsm[f'X_{basis}'] = adata_proc.obsm[f'X_{basis}'].copy()
                 print(f"Copied embedding 'X_{basis}' from processed data.")
                 results_summary['embedding_basis_found'] = basis
            else:
                 print(f"Warning: Embedding 'X_{basis}' not found in processed data. Velocity embedding plots will fail.")
                 results_summary['embedding_basis_found'] = None


            # Neighbors graph (needed for moments and velocity graph):
            if 'neighbors' in adata_proc.uns:
                 adata_for_velocity.uns['neighbors'] = adata_proc.uns['neighbors'].copy()
                 # Also copy connectivities/distances if they exist and are needed
                 if 'connectivities' in adata_proc.obsp:
                      adata_for_velocity.obsp['connectivities'] = adata_proc.obsp['connectivities'].copy()
                 if 'distances' in adata_proc.obsp:
                      adata_for_velocity.obsp['distances'] = adata_proc.obsp['distances'].copy()
                 print("Copied 'neighbors' graph (and potentially connectivities/distances) from processed data.")
                 results_summary['neighbors_graph_found'] = True
            else:
                 # If no neighbors graph, moments need to be calculated
                 print("Warning: Neighbors graph not found in processed data. Calculating moments...")
                 # Need PCA for moments - copy it or recalculate? Copy if exists.
                 if 'X_pca' in adata_proc.obsm:
                     adata_for_velocity.obsm['X_pca'] = adata_proc.obsm['X_pca'].copy()
                     n_pcs_moments = min(30, adata_for_velocity.obsm['X_pca'].shape[1])
                 else: # Recalculate PCA if not found
                     sc.tl.pca(adata_for_velocity)
                     n_pcs_moments = min(30, adata_for_velocity.obsm['X_pca'].shape[1])

                 scv.pp.moments(adata_for_velocity, n_pcs=n_pcs_moments, n_neighbors=30) # Use default neighbors for moments
                 results_summary['neighbors_graph_found'] = False


            # Clustering (for coloring plots):
            color_key = params.get('color_key')
            if color_key and color_key in adata_proc.obs:
                 adata_for_velocity.obs[color_key] = adata_proc.obs[color_key].copy()
                 print(f"Copied coloring key '{color_key}' from processed data.")
                 results_summary['color_key_found'] = color_key
            else:
                 # Check default 'clusters'
                 if 'clusters' in adata_proc.obs:
                      adata_for_velocity.obs['clusters'] = adata_proc.obs['clusters'].copy()
                      params['color_key'] = 'clusters' # Update effective color key
                      print(f"Copied coloring key 'clusters' from processed data.")
                      results_summary['color_key_found'] = 'clusters'
                 else:
                      print(f"Warning: Specified color key '{color_key}' or default 'clusters' not found in processed data.")
                      params['color_key'] = None # Disable coloring
                      results_summary['color_key_found'] = None


            # Free memory
            del adata_orig
            del adata_proc

        # --- Velocity Preprocessing (on the merged object if applicable) ---
        # Basic filtering/normalization might have been done before, but velocity often benefits
        # from its own gene selection based on velocity dynamics.
        # This step is optional and depends on the desired workflow.
        # if not adata_proc: # Only run if we started from original data only
        #     self.update_state(state='PROGRESS', meta={'status': 'Preprocessing for velocity...', 'step': 3, 'total_steps': 7})
        #     # Filter genes based on counts - might be redundant if basic analysis did it
        #     # scv.pp.filter_genes(adata_for_velocity, min_shared_counts=params.get('min_shared_counts', 20))
        #     # Normalize per cell
        #     # scv.pp.normalize_per_cell(adata_for_velocity)
        #     # Filter genes by dispersion / select HVGs relevant for velocity
        #     # scv.pp.filter_genes_dispersion(adata_for_velocity, n_top_genes=params.get('n_top_genes', 2000))
        #     # Log transform
        #     # scv.pp.log1p(adata_for_velocity)
        #     # Calculate moments (neighbors, pca needed) - Done above if neighbors were missing
        #     # scv.pp.moments(adata_for_velocity, n_pcs=30, n_neighbors=30)
        #     print("Skipping velocity preprocessing as processed data was loaded.")
        # else:
        #     print("Using moments from merged/processed data.")
        # Ensure moments are calculated if neighbors were present but moments weren't run
        if 'neighbors' in adata_for_velocity.uns and 'pca' not in adata_for_velocity.uns: # Check if moments were calculated
            print("Neighbors graph found, ensuring moments are calculated...")
            # Check if PCs exist for moments calculation
            if 'X_pca' not in adata_for_velocity.obsm:
                 raise ValueError("PCA embedding ('X_pca') needed for moments calculation is missing.")
            n_pcs_moments = min(30, adata_for_velocity.obsm['X_pca'].shape[1])
            scv.pp.moments(adata_for_velocity, n_pcs=n_pcs_moments, n_neighbors=params.get('vgraph_n_neighbors', 30)) # Use consistent neighbors?


        # 3. Recover Dynamics / Calculate Velocity
        # Depends on the chosen mode. Dynamical is most complex.
        mode = params.get('mode', 'stochastic')
        self.update_state(state='PROGRESS', meta={'status': f'Calculating Velocity (mode: {mode})...', 'step': 4, 'total_steps': 7})
        if mode == 'dynamical':
            # Requires moments calculated
            scv.tl.recover_dynamics(adata_for_velocity, fit_basal_transcription=params.get('fit_basal_transcription', True), n_jobs=4) # Use more cores if available
        # Stochastic and Deterministic modes calculate velocity directly
        # Need to ensure velocity genes are selected appropriately beforehand if not using dynamical
        scv.tl.velocity(adata_for_velocity, mode=mode)
        results_summary['velocity_calculated'] = {'mode': mode}


        # 4. Calculate Velocity Graph
        self.update_state(state='PROGRESS', meta={'status': 'Calculating Velocity Graph...', 'step': 5, 'total_steps': 7})
        scv.tl.velocity_graph(adata_for_velocity, n_neighbors=params.get('vgraph_n_neighbors'), approx=params.get('vgraph_approx'), n_jobs=4)
        results_summary['velocity_graph_calculated'] = True


        # 5. Generate Velocity Embedding Plots
        # Check if the embedding actually exists before plotting
        embedding_key = f'X_{basis}'
        # print(adata_for_velocity)
        if embedding_key in adata_for_velocity.obsm:
            self.update_state(state='PROGRESS', meta={'status': f'Generating Velocity Plots ({basis})...', 'step': 6, 'total_steps': 7})
            color_arg = params.get('color_key') if params.get('color_key') in adata_for_velocity.obs else None # Use validated color key

            # --- Grid Plot ---
            try:
                filename = f"{plot_base_name}_grid_{data_id}_{uuid.uuid4()}.png"
                fig_grid = scv.pl.velocity_embedding_grid(
                    adata_for_velocity, basis=basis, color=color_arg,
                    save=filename, # Temp filename
                    show=False, title=f'Velocity Grid ({basis})'
                )
                # Move plot (scvelo save behavior might differ, adjust path if needed)#TODO change it maybe
                temp_grid_path = Path(scv.settings.figdir) / f"scvelo_{filename}" # Check exact saved name pattern
                if temp_grid_path.exists():
                     temp_grid_path.rename(grid_plot_path)
                     results_summary['grid_plot_path'] = str(grid_plot_path)
                     print(f"Saved grid plot to {grid_plot_path}")
                else:
                      # Try scanpy's default naming pattern as fallback
                      temp_grid_path_alt = Path(scv.settings.figdir) / f"{filename}"
                      if temp_grid_path_alt.exists():
                          temp_grid_path_alt.rename(grid_plot_path)
                          results_summary['grid_plot_path'] = str(grid_plot_path)
                          print(f"Saved grid plot (alt name) to {grid_plot_path}")
                      else:
                          print(f"Warning: Velocity grid plot file not found at {temp_grid_path} or {temp_grid_path_alt}")

                plt.close('all') # Close figures
            except Exception as plot_err:
                print(f"Warning: Could not generate velocity grid plot: {plot_err}\n{traceback.format_exc()}")
                results_summary['grid_plot_path'] = None

            # --- Stream Plot ---
            try:
                fig_stream = scv.pl.velocity_embedding_stream(
                    adata_for_velocity, basis=basis, color=color_arg,
                    save=f'_{plot_base_name}_stream_{data_id}_{uuid.uuid4()}.png', # Temp filename
                    show=False, title=f'Velocity Stream ({basis})'
                )
                temp_stream_path = Path(scv.settings.figdir) / f"scvelo_{plot_base_name}_stream_{data_id}_{uuid.uuid4()}.png" # Check exact name
                if temp_stream_path.exists():
                     temp_stream_path.rename(stream_plot_path)
                     results_summary['stream_plot_path'] = str(stream_plot_path)
                     print(f"Saved stream plot to {stream_plot_path}")
                else:
                      temp_stream_path_alt = Path(scv.settings.figdir) / f"{plot_base_name}_stream_{data_id}_{uuid.uuid4()}.png"
                      if temp_stream_path_alt.exists():
                          temp_stream_path_alt.rename(stream_plot_path)
                          results_summary['stream_plot_path'] = str(stream_plot_path)
                          print(f"Saved stream plot (alt name) to {stream_plot_path}")
                      else:
                           print(f"Warning: Velocity stream plot file not found at {temp_stream_path} or {temp_stream_path_alt}")

                plt.close('all')
            except Exception as plot_err:
                print(f"Warning: Could not generate velocity stream plot: {plot_err}\n{traceback.format_exc()}")
                results_summary['stream_plot_path'] = None

        else:
            print(f"Skipping velocity embedding plots as basis '{basis}' (key '{embedding_key}') was not found.")
            self.update_state(state='PROGRESS', meta={'status': f'Skipping plots (basis {basis} missing)...', 'step': 6, 'total_steps': 7})


        # 6. Save Updated AnnData (Optional)
        if params.get('save_updated_adata', False):
             self.update_state(state='PROGRESS', meta={'status': 'Saving AnnData with velocity...', 'step': 7, 'total_steps': 7})
             try:
                 # Save the adata object containing velocity results
                 adata_for_velocity.write(updated_adata_path, compression="gzip")
                 results_summary['updated_adata_path'] = str(updated_adata_path)
                 print(f"Saved AnnData with velocity results to {updated_adata_path}")
             except Exception as write_err:
                  print(f"Warning: Failed to save AnnData with velocity results: {write_err}")
                  results_summary['updated_adata_path'] = None
        else:
             self.update_state(state='PROGRESS', meta={'status': 'Skipping final save...', 'step': 7, 'total_steps': 7})

        return {'status': 'Complete', 'results_summary': results_summary}

    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"An unexpected error occurred during RNA Velocity analysis: {e}")
        print(error_traceback)
        self.update_state(state='FAILURE', meta={'status': 'Error during RNA Velocity analysis', 'error': str(e), 'traceback': error_traceback})
        raise e # Re-raise so Celery marks as failed
    finally:
         plt.close('all') # Ensure all plots are closed
         # Clean up temp figure files if needed