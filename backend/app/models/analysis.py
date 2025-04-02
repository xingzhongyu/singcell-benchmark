# backend/app/models/analysis.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

class AnalysisParams(BaseModel):
    # QC Params (Example: fixed mito prefix, adjustable thresholds)
    mito_prefix: str = Field("MT-", description="Prefix for mitochondrial genes (case-sensitive)")
    min_genes_after_qc: int = Field(200, description="Min genes per cell after basic filtering")
    min_cells_after_qc: int = Field(3, description="Min cells per gene after basic filtering")
    # qc_max_genes: Optional[int] = Field(None, description="Max genes per cell (optional QC filter)")
    # qc_max_pct_mito: Optional[float] = Field(None, description="Max mitochondrial percentage (optional QC filter)")

    # HVG Selection
    select_hvgs: bool = Field(True, description="Whether to select Highly Variable Genes")
    hvg_min_mean: float = Field(0.0125, description="HVG selection: min mean expression")
    hvg_max_mean: float = Field(3.0, description="HVG selection: max mean expression")
    hvg_min_disp: float = Field(0.5, description="HVG selection: min dispersion")
    hvg_n_top_genes: Optional[int] = Field(None, description="Alternatively, select top N HVGs (overrides mean/disp)")

    # Normalization & Scaling (Optional: Add scaling params if needed)
    normalize_target_sum: Optional[float] = Field(1e4, description="Target sum for normalization (None to skip)")
    # scale_max_value: Optional[float] = Field(10.0, description="Max value after scaling (optional)")

    # PCA
    pca_n_comps: int = Field(50, description="Number of principal components")

    # Neighbors
    neighbors_n_pcs: int = Field(30, description="Number of PCs to use for neighbors calculation")
    neighbors_n_neighbors: int = Field(15, description="Number of neighbors for graph construction") # Increased default

    # UMAP (Keep defaults, maybe add min_dist, spread later)
    umap_min_dist: float = Field(0.5, description="UMAP minimum distance")
    umap_spread: float = Field(1.0, description="UMAP spread")


    # Clustering
    clustering_method: Literal['leiden', 'louvain'] = Field('leiden', description="Clustering algorithm")
    leiden_resolution: float = Field(0.5, description="Resolution for Leiden clustering")
    louvain_resolution: float = Field(0.5, description="Resolution for Louvain clustering")

    # Marker Genes
    marker_gene_method: Literal['t-test', 'wilcoxon'] = Field('wilcoxon', description="Method for marker gene detection")
    marker_gene_n_genes: int = Field(25, description="Number of top marker genes to report per cluster")


class TaskResponse(BaseModel):
    task_id: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    
from pydantic import BaseModel, Field, FilePath
from typing import Optional, Dict, Any, Literal, List

# --- Integration Models ---
class IntegrationFile(BaseModel):
    data_id: str
    batch_label: str

class IntegrationParams(BaseModel):
    integration_method: Literal['bbknn', 'harmony'] = Field('bbknn', description="Integration method")
    files: List[IntegrationFile] = Field(..., description="List of dataset IDs and their batch labels")
    output_data_id: Optional[str] = Field(None, description="Optional specific ID for the output integrated data (defaults to UUID)") # Allow specifying output ID

    # BBKNN specific params (add more as needed)
    bbknn_batch_key: str = Field('batch', description="adata.obs key for batch info in BBKNN")
    bbknn_neighbors_within_batch: int = Field(3, description="BBKNN neighbors within batch")

    # Harmony specific params (add more as needed)
    harmony_batch_key: str = Field('batch', description="adata.obs key for batch info in Harmony")
    harmony_theta: float = Field(2.0, description="Harmony diversity clustering penalty parameter")
    harmony_max_iter_harmony: int = Field(10, description="Harmony max iterations")

    # Post-integration steps (run on integrated object)
    run_pca: bool = Field(True, description="Run PCA on the integrated representation (Harmony) or corrected graph (BBKNN)")
    pca_n_comps: int = Field(50, description="Number of PCs")
    run_neighbors: bool = Field(True, description="Calculate neighbors on integrated PCA/graph")
    neighbors_n_pcs: int = Field(30, description="Number of PCs for neighbors")
    neighbors_n_neighbors: int = Field(15, description="Number of neighbors")
    run_umap: bool = Field(True, description="Run UMAP on integrated neighbors")
    umap_min_dist: float = Field(0.5, description="UMAP min_dist")
    umap_spread: float = Field(1.0, description="UMAP spread")

# --- Trajectory Models ---
class TrajectoryParams(BaseModel):
    source_data_id: str = Field(..., description="Data ID of the processed AnnData to use")
    run_diffmap: bool = Field(True, description="Run Diffusion Map")
    diffmap_n_comps: int = Field(15, description="Number of diffusion components")
    run_paga: bool = Field(True, description="Run PAGA")
    paga_clustering_key: str = Field("clusters", description="adata.obs key containing cluster labels for PAGA") # Ensure this key exists
    paga_threshold_connectivities: float = Field(0.05, description="PAGA connectivities threshold")
    paga_threshold_confidence: float = Field(0.01, description="PAGA confidence threshold")
    calculate_dpt: bool = Field(True, description="Calculate Diffusion Pseudotime (DPT)")
    dpt_root_cluster: Optional[str] = Field(None, description="Cluster label to use as root for DPT (required if calculate_dpt is True)") # User must specify root


# --- Cell Communication Models ---
class CellCommunicationParams(BaseModel):
    source_data_id: str = Field(..., description="Data ID of the processed AnnData to use")
    clustering_key: str = Field("clusters", description="adata.obs key containing cluster labels") # Ensure this key exists
    cellphonedb_database_path: Optional[str] = Field(None, description="Path to the downloaded CellPhoneDB database directory") # Needs configuration!
    counts_layer: Optional[str] = Field(None, description="Layer in AnnData containing normalized, non-log counts (if None, uses .X)")
    gene_id_column: Optional[str] = Field(None, description="adata.var column containing gene identifiers (e.g., HGNC symbols) if not index")
    output_path_suffix: str = Field("cellphonedb_out", description="Suffix for CellPhoneDB output directory within results")
    threads: int = Field(4, description="Number of threads for CellPhoneDB")
    subsampling: bool = Field(False, description="Enable CellPhoneDB subsampling")
    subsampling_num_pc: int = Field(100, description="Subsampling: number of PCs")
    subsampling_log: bool = Field(False, description="Subsampling: log transform") # CellphoneDB default is False
    
# --- RNA Velocity Models ---
class RnaVelocityParams(BaseModel):
    source_data_id: str = Field(..., description="Data ID of the AnnData object containing spliced/unspliced layers")
    # Preprocessing options within velocity task (optional, usually done beforehand)
    # min_shared_counts: int = Field(20, description="scVelo: Min shared spliced/unspliced counts for velocity gene filtering")
    # n_top_genes: Optional[int] = Field(2000, description="scVelo: Select top N velocity genes (None to use all)")

    # Core velocity calculation
    mode: Literal['stochastic', 'deterministic', 'dynamical'] = Field('stochastic', description="scVelo: Mode for velocity calculation")
    fit_basal_transcription: bool = Field(True, description="scVelo (Dynamical): Fit basal transcription") # Only for dynamical mode

    # Velocity graph
    vgraph_n_neighbors: Optional[int] = Field(None, description="scVelo: Number of neighbors for velocity graph (None uses default from existing neighbors graph)")
    vgraph_approx: Optional[bool] = Field(None, description="scVelo: Use approximate nearest neighbors for velocity graph")

    # Embedding options
    embedding_basis: str = Field("umap", description="Basis for embedding velocity (e.g., 'umap', 'tsne', 'pca') - must exist in adata.obsm")
    color_key: Optional[str] = Field("clusters", description="adata.obs key for coloring velocity plot (e.g., 'clusters', 'batch')")

    # Output options
    save_updated_adata: bool = Field(False, description="Save the AnnData object with velocity results added")