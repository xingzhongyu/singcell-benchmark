# backend/app/tasks/communication_tasks.py
import scanpy as sc
import anndata as ad
import os
import uuid
import matplotlib.pyplot as plt
import pandas as pd
import shutil # For copying/removing files
from pathlib import Path
import traceback # For detailed error logging

# --- Import CellPhoneDB Core Method ---
# Make sure cellphonedb package (v5+) is installed in the environment
try:
    from cellphonedb.src.core.methods import cpdb_statistical_analysis_method
    # Potentially import plotting functions if needed later
    # from cellphonedb.core.plotting import dot_plot, heatmap_plot
except ImportError:
    print("ERROR: CellPhoneDB package not found or import failed. Please ensure it's installed.")
    cpdb_statistical_analysis_method = None # Set to None to handle gracefully later

from ..core.config import RESULT_DIR_STR, CPDB_DATABASE_PATH # Import configured DB path
from celery_app import celery_app

# Optional: Add plotting dependencies if generating plots from CPDB output
# import seaborn as sns
# from adjustText import adjust_text

@celery_app.task(bind=True, name='app.tasks.communication_tasks.run_cellphone_analysis')
def run_cellphone_analysis(self, params: dict):
    """ Celery task to run CellPhoneDB analysis using its Python API. """
    if cpdb_statistical_analysis_method is None:
         raise ImportError("CellPhoneDB library failed to import. Cannot run analysis.")

    self.update_state(state='STARTED', meta={'status': 'Starting Cell Communication Analysis...'})

    data_id = params['source_data_id']
    result_data_dir = Path(RESULT_DIR_STR) / data_id
    source_adata_path_proc = result_data_dir / f"{data_id}_processed.h5ad"
    source_adata_path_int = result_data_dir / f"{data_id}_integrated.h5ad"
    
    if source_adata_path_proc.exists():
         source_adata_path = source_adata_path_proc
    elif source_adata_path_int.exists():
         source_adata_path = source_adata_path_int
    else:
         raise FileNotFoundError(f"Source AnnData not found for ID {data_id}")

    output_suffix = params.get('output_path_suffix', 'cellphonedb_out')
    cpdb_output_dir = result_data_dir / output_suffix
    cpdb_output_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = result_data_dir / "temp_cpdb_input"
    temp_dir.mkdir(parents=True, exist_ok=True)
    meta_path = temp_dir / "meta.tsv"
    # CellPhoneDB library function might prefer specific formats, h5ad is often convenient
    counts_path = temp_dir / "counts.h5ad"

    # --- Get Database Path from Configuration ---
    # IMPORTANT: Do NOT rely on params['cellphonedb_database_path'] from frontend
    # Use the path configured on the server (via config.py or env var)
    cellphone_db_path_obj=CPDB_DATABASE_PATH if params.get('cellphonedb_database_path') is None else params.get('cellphonedb_database_path')
    if not cellphone_db_path_obj.exists():
         # Check if the zipped version exists maybe? Or just error out.
         raise FileNotFoundError(f"Configured CellPhoneDB database directory not found or invalid: {cellphone_db_path_obj}")

    results_summary = {'source_data_id': data_id, 'cpdb_output_dir': str(cpdb_output_dir)}

    try:
        # 1. Load Data
        self.update_state(state='PROGRESS', meta={'status': 'Loading data...', 'step': 1, 'total_steps': 5})
        adata = sc.read_h5ad(source_adata_path)

        cluster_key = params.get('clustering_key', 'clusters')
        if cluster_key not in adata.obs:
             raise ValueError(f"Clustering key '{cluster_key}' not found in adata.obs.")

        # 2. Prepare Input Files (Metadata and Counts)
        self.update_state(state='PROGRESS', meta={'status': 'Preparing CellPhoneDB inputs...', 'step': 2, 'total_steps': 5})

        # --- Metadata File ---
        meta_df = pd.DataFrame({
            'Cell': adata.obs_names,
            'cell_type': adata.obs[cluster_key].astype(str)
        })
        meta_df.to_csv(meta_path, sep='\t', index=False)
        results_summary['meta_file_generated'] = str(meta_path)

        # --- Counts File (Prepare AnnData for export) ---
        counts_layer = params.get('counts_layer')
        gene_id_col = params.get('gene_id_column') # e.g., 'hgnc_symbol' if not in index

        if counts_layer and counts_layer in adata.layers:
             counts_matrix = adata.layers[counts_layer].copy()
             print(f"Using counts from layer: {counts_layer}")
        else:
             counts_matrix = adata.X.copy()
             print(f"Using counts from adata.X")

        # Determine gene identifiers to use (needs to match CellPhoneDB database, usually HGNC)
        if gene_id_col and gene_id_col in adata.var:
             var_index_for_cpdb = adata.var[gene_id_col].astype(str)
             print(f"Using gene identifiers from column: {gene_id_col}")
             # Check for duplicates if using a column
             if not var_index_for_cpdb.is_unique:
                 print(f"Warning: Gene identifiers in column '{gene_id_col}' are not unique. Attempting to make unique.")
                 var_index_for_cpdb = ad.utils.make_index_unique(pd.Index(var_index_for_cpdb))
                 print("Note: Duplicates were renamed. This might affect results if original names were critical.")
        else:
             var_index_for_cpdb = adata.var_names # Use .var_names (index)
             print(f"Using gene identifiers from AnnData index (.var_names)")
             # Assume index is already unique and appropriate (e.g., HGNC symbols)

        # Create the temporary AnnData for export with the correct gene identifiers in the index
        # CellPhoneDB expects genes in rows (.var) and cells in columns (.obs)
        counts_adata = ad.AnnData(X=counts_matrix, obs=adata.obs.copy())
        counts_adata.var = pd.DataFrame(index=var_index_for_cpdb) # Set the correct index
        counts_adata.var_names_make_unique() # Ensure index is unique just in case

        # Write temporary counts file (h5ad is often easiest for the library)
        counts_adata.write_h5ad(counts_path)
        results_summary['counts_file_generated'] = str(counts_path)
        del counts_adata # Free memory

        # Determine counts_data argument (how genes are identified)
        # This depends on what's in var_index_for_cpdb. Assume 'hgnc_symbol' if not specified.
        counts_data_type = params.get('counts_data_type', 'hgnc_symbol') # Add param if needed, default HGNC

        # 3. Run CellPhoneDB Method using the library function
        self.update_state(state='PROGRESS', meta={'status': 'Running CellPhoneDB analysis method...', 'step': 3, 'total_steps': 5})
        print(f"Starting CellPhoneDB statistical analysis...")
        print(f"  Meta file: {meta_path}")
        print(f"  Counts file: {counts_path}")
        print(f"  Database path: {cellphone_db_path_obj}")
        print(f"  Output path: {cpdb_output_dir}")
        print(f"  Threads: {params.get('threads', 4)}")
        # Add other params being used to the log

        try:
            cpdb_statistical_analysis_method.call(
                cpdb_file_path=cellphone_db_path_obj, # Path to DIRECTORY containing db files
                meta_file_path=meta_path,
                counts_file_path=counts_path,
                counts_data=counts_data_type, # Type of gene identifier in counts_file index
                output_path=cpdb_output_dir,
                threads=params.get('threads', 4),
                subsampling=params.get('subsampling', False),
                subsampling_log=params.get('subsampling_log', False), # Default is False
                subsampling_num_pc=params.get('subsampling_num_pc', 100),
                # Optional: Add other parameters exposed by the function if needed
                # iterations = 1000,
                # threshold = 0.1,
                # debug = False,
                # result_precision = 3,
            )
            print("CellPhoneDB statistical analysis completed successfully.")
            results_summary['cellphonedb_run_success'] = True

        except Exception as cpdb_error:
            # Catch specific CellPhoneDB errors if possible, otherwise general Exception
            error_traceback = traceback.format_exc()
            print(f"ERROR during CellPhoneDB execution: {cpdb_error}")
            print(error_traceback)
            results_summary['cellphonedb_run_success'] = False
            raise ValueError(f"CellPhoneDB analysis failed: {cpdb_error}") # Re-raise to fail the task


        # 4. Generate Plots (Optional - Using CellPhoneDB's plotting functions)
        # This requires CellPhoneDB's output files to exist.
        significant_means_path = cpdb_output_dir / 'significant_means.txt'
        pvalues_path = cpdb_output_dir / 'pvalues.txt'
        if significant_means_path.exists() and pvalues_path.exists():
             self.update_state(state='PROGRESS', meta={'status': 'Generating communication plots...', 'step': 4, 'total_steps': 5})
             print("Attempting to generate CellPhoneDB plots...")
             try:
                 # --- Example: Dot Plot ---
                 # Need to import: from cellphonedb.core.plotting import dot_plot
                 # dot_plot.call(
                 #     means_path=significant_means_path,
                 #     pvalues_path=pvalues_path,
                 #     output_path=cpdb_output_dir,
                 #     output_name='dot_plot.png', # or .pdf
                 #     # Add optional parameters like rows/columns paths if needed
                 # )
                 # print("Generated dot plot.")

                 # --- Example: Heatmap Plot ---
                 # Need to import: from cellphonedb.core.plotting import heatmap_plot
                 # heatmap_plot.call(
                 #      meta_file=meta_path, # Often needs meta again
                 #      pvalues_path=pvalues_path,
                 #      output_path=cpdb_output_dir,
                 #      output_name = 'heatmap_count.png', # or .pdf
                 #      count_network = True, # Plot counts instead of p-values/means
                 #      # Add optional parameters
                 # )
                 # print("Generated heatmap plot.")

                 print("Note: CellPhoneDB plot generation within task is currently commented out.")
                 results_summary['plots_generated'] = False # Set to True if plots are actually generated

             except Exception as plot_error:
                 print(f"Warning: Failed to generate plots from CellPhoneDB results: {plot_error}")
                 results_summary['plots_generated'] = False
        else:
             print("Warning: CellPhoneDB output files (significant_means.txt, pvalues.txt) not found. Skipping plot generation.")
             results_summary['plots_generated'] = False


        # 5. Clean up temporary input files
        self.update_state(state='PROGRESS', meta={'status': 'Cleaning up...', 'step': 5, 'total_steps': 5})
        try:
            shutil.rmtree(temp_dir)
            print(f"Removed temporary directory: {temp_dir}")
        except OSError as e:
            print(f"Warning: Could not remove temporary directory {temp_dir}: {e}")

        return {'status': 'Complete', 'results_summary': results_summary}

    except Exception as e:
        # General error handling
        error_traceback = traceback.format_exc()
        print(f"An unexpected error occurred: {e}")
        print(error_traceback)
        # Clean up temp dir on failure too
        if temp_dir.exists():
             try: shutil.rmtree(temp_dir)
             except OSError: pass
        self.update_state(state='FAILURE', meta={'status': 'Error during cell communication analysis', 'error': str(e), 'traceback': error_traceback})
        raise e # Re-raise so Celery marks as failed
    finally:
         plt.close('all') # Close any matplotlib figures just in case