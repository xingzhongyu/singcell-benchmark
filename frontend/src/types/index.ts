// frontend/src/types/index.ts

export interface UploadResponse {
  data_id: string;
  filename: string;
}

export interface TaskStartResponse {
  task_id: string;
}

// More detailed status from Celery task meta
interface TaskProgressMeta {
    status: string;
    step?: number;
    total_steps?: number;
    error?: string;
    traceback?: string; // Include traceback on failure
}

// Summary returned by the task upon SUCCESS
export interface AnalysisResultsSummary {
    original_shape?: { obs: number; var: number };
    qc_calculated?: boolean;
    qc_plot_path?: string | null; // Path or null if failed
    shape_after_basic_filter?: { obs: number; var: number };
    normalized?: boolean;
    hvg_calculated?: boolean;
    shape_after_hvg?: { obs: number; var: number };
    scaled?: boolean; // If scaling is added
    pca_done?: boolean;
    neighbors_done?: boolean;
    umap_done?: boolean;
    clustering_done?: { method: string; resolution: number };
    marker_genes_calculated?: boolean;
    marker_genes_path?: string | null; // Path or null if failed
    umap_plot_path?: string | null; // Path or null if failed
    processed_data_path?: string;
    marker_gene_method?: string;
}

interface TaskSuccessResult {
    status: 'Complete';
    results_summary: AnalysisResultsSummary;
}

interface TaskFailureResult extends TaskProgressMeta {
    // May contain error and traceback from meta
}


export interface TaskStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';
  // result can be meta during progress/failure, or the final summary on success
  result?: TaskProgressMeta | TaskSuccessResult | TaskFailureResult | null | any;
}

export interface AnalysisParameters {
    // QC
    mito_prefix: string;
    min_genes_after_qc: number;
    min_cells_after_qc: number;
    // HVG
    select_hvgs: boolean;
    hvg_min_mean: number;
    hvg_max_mean: number;
    hvg_min_disp: number;
    hvg_n_top_genes: number | null; // Use null for 'not set'
    // Normalization
    normalize_target_sum: number | null; // Use null for skip
    // PCA
    pca_n_comps: number;
    // Neighbors
    neighbors_n_pcs: number;
    neighbors_n_neighbors: number;
    // UMAP
    umap_min_dist: number;
    umap_spread: number;
    // Clustering
    clustering_method: 'leiden' | 'louvain';
    leiden_resolution: number;
    louvain_resolution: number;
    // Markers
    marker_gene_method: 't-test' | 'wilcoxon';
    marker_gene_n_genes: number;
}

// For Marker Gene Table Data (from JSON endpoint)
export interface MarkerGene {
    names: string; // Gene name
    scores?: number; // Score (e.g., Wilcoxon U or t-statistic)
    logfoldchanges?: number; // Log fold change
    pvals?: number; // Raw p-value
    pvals_adj?: number; // Adjusted p-value
    group: string; // Cluster group
    // Add other columns as needed based on rank_genes_groups output
    [key: string]: any; // Allow for extra columns
}

// For Gene Expression Plot Data
export interface GeneExpressionResponse {
    gene_name: string;
    umap_coordinates: [number, number][]; // Array of [x, y] pairs
    expression: number[]; // Array of expression values, same order as coords
    clusters?: (string | number)[]; // Optional cluster assignments
    cell_ids: string[]; // Cell IDs corresponding to coords/expression
}

// --- Integration ---
export interface IntegrationFile {
  data_id: string;
  batch_label: string;
}

export interface IntegrationParameters {
  integration_method: 'bbknn' | 'harmony';
  files: IntegrationFile[];
  output_data_id?: string; // Optional
  bbknn_batch_key: string;
  bbknn_neighbors_within_batch: number;
  harmony_batch_key: string;
  harmony_theta: number;
  harmony_max_iter_harmony: number;
  run_pca: boolean;
  pca_n_comps: number;
  run_neighbors: boolean;
  neighbors_n_pcs: number;
  neighbors_n_neighbors: number;
  run_umap: boolean;
  umap_min_dist: number;
  umap_spread: number;
}

export interface IntegrationResultsSummary {
  integrated_data_id: string;
  concatenated_shape?: { obs: number; var: number };
  pca_on_concatenated?: boolean;
  integration_method?: 'bbknn' | 'harmony';
  neighbors_done?: boolean;
  umap_done?: boolean;
  umap_batch_plot_path?: string | null;
  umap_clusters_plot_path?: string | null; // If calculated
  integrated_data_path?: string;
}

// --- Trajectory ---
export interface TrajectoryParameters {
  source_data_id: string;
  run_diffmap: boolean;
  diffmap_n_comps: number;
  run_paga: boolean;
  paga_clustering_key: string;
  paga_threshold_connectivities: number;
  paga_threshold_confidence: number;
  calculate_dpt: boolean;
  dpt_root_cluster?: string | null; // Nullable if DPT not calculated
}

export interface TrajectoryResultsSummary {
  source_data_id: string;
  diffmap_done?: boolean;
  diffmap_plot_path?: string | null;
  paga_done?: boolean;
  paga_graph_plot_path?: string | null;
  paga_umap_plot_path?: string | null;
  dpt_calculated?: boolean;
  dpt_root_index_used?: number;
  dpt_umap_plot_path?: string | null;
  // updated_adata_path?: string; // If saved
}

// --- Cell Communication ---
export interface CellCommunicationParameters {
  source_data_id: string;
  clustering_key: string;
  // Database path likely configured server-side, maybe not sent from frontend
  // cellphonedb_database_path: string;
  counts_layer?: string | null;
  gene_id_column?: string | null;
  output_path_suffix: string;
  threads: number;
  subsampling: boolean;
  subsampling_num_pc: number;
  subsampling_log: boolean;
}

export interface CellCommunicationResultsSummary {
  source_data_id: string;
  cpdb_output_dir?: string;
  meta_file_generated?: string;
  counts_file_generated?: string;
  cellphonedb_run_success?: boolean;
  cellphonedb_stdout?: string;
  cellphonedb_stderr?: string;
  plots_generated?: boolean; // If plotting is implemented
  // Add paths to specific plots if generated
}


// Update TaskStatus result to potentially hold different summary types
export interface TaskStatus {
task_id: string;
// Add task type? Might be useful for frontend logic
// task_type: 'basic' | 'integration' | 'trajectory' | 'communication';
status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';
result?: TaskProgressMeta | { status: 'Complete'; results_summary: AnalysisResultsSummary | IntegrationResultsSummary | TrajectoryResultsSummary | CellCommunicationResultsSummary } | TaskFailureResult | null | any;
}

// Type to manage state for different analysis types run on a dataset
export interface DatasetAnalysisState {
  taskId: string | null;
  status: TaskStatus | null;
  parameters?: any; // Store params used for this specific run
  resultsSummary?: any; // Store specific summary on success
  error?: string | null;
}

export interface AppDatasetState {
  dataId: string; // Original or Integrated Data ID
  filename?: string; // Original filename if applicable
  isIntegrated: boolean; // Flag if this is an integrated dataset
  uploadTime?: string; // Optional timestamp
  // Status/Results for each analysis type run on this dataId
  basicAnalysis?: DatasetAnalysisState;
  trajectoryAnalysis?: DatasetAnalysisState;
  communicationAnalysis?: DatasetAnalysisState;
  integrationAnalysis?:DatasetAnalysisState;
  // Store source IDs if integrated
  sourceDataIds?: string[];
  batchLabel?:string;
}