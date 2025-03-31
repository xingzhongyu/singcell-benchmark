export interface UploadResponse {
    data_id: string;
    filename: string;
  }
  
  export interface TaskStartResponse {
    task_id: string;
  }
  
  export interface TaskStatus {
    task_id: string;
    status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED';
    result?: any; // Can be more specific based on expected results or errors
  }
  
  export interface AnalysisParameters {
      min_genes: number;
      min_cells: number;
      pca_n_comps: number;
      neighbors_n_pcs: number;
      leiden_resolution: number;
  }