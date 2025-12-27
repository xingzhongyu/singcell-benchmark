// frontend/src/services/api.ts
import axios from 'axios';
import {
    UploadResponse, TaskStartResponse, TaskStatus, AnalysisParameters,
    MarkerGene, GeneExpressionResponse,
    IntegrationParameters, TrajectoryParameters, CellCommunicationParameters,
    IntegrationResultsSummary, TrajectoryResultsSummary, CellCommunicationResultsSummary, AppDatasetState, // Add AppDatasetState if used for complex state
    RnaVelocityParameters,
    AtacAnalysisParameters,
    GRNEdge, DeepSEMParameters
} from '../types';

// Adjust if your backend runs on a different port or host
// Use environment variables in a real app: process.env.REACT_APP_API_URL || 'http://localhost:8000/api'
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://211.87.232.159:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Upload ---
export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await apiClient.post('/data/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (error) {
    console.error("Upload error:", error);
    if (axios.isAxiosError(error) && error.response) {
        throw new Error(error.response.data.detail || 'File upload failed');
    }
    throw new Error('File upload failed due to an unknown error');
  }
};

// --- Analysis Task ---
export const startAnalysis = async (dataId: string, params: AnalysisParameters): Promise<TaskStartResponse> => {
    try {
        // Ensure numeric fields that can be null are handled correctly
        const payload = {
            ...params,
            hvg_n_top_genes: params.hvg_n_top_genes === 0 ? null : params.hvg_n_top_genes, // Allow 0 but treat as null if intended as 'unset'
            normalize_target_sum: params.normalize_target_sum === 0 ? null : params.normalize_target_sum,
        };
        const response = await apiClient.post(`/analysis/analyze/${dataId}`, payload);
        return response.data;
    } catch (error) {
        console.error("Start analysis error:", error);
        if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to start analysis');
        }
        throw new Error('Failed to start analysis due to an unknown error');
    }
};

export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
    try {
        const response = await apiClient.get(`/analysis/status/${taskId}`);
        // TODO: Add more specific type checking/casting for response.data.result
        // based on status (PROGRESS, SUCCESS, FAILURE) if needed downstream.
        return response.data as TaskStatus;
    } catch (error) {
        console.error("Get status error:", error);
         if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to get task status');
        }
        throw new Error('Failed to get task status due to an unknown error');
    }
};

// --- Result URLs ---

// Function to get the URL for the result image - NOW DYNAMIC
export const getUmapPlotUrl = (dataId: string, clusterMethod: string): string => {
    if (!dataId || !clusterMethod) return ""; // Handle missing params
    // Add timestamp to prevent caching issues, especially during development
    return `${API_BASE_URL}/data/results/${dataId}/plot/umap/${clusterMethod}?t=${new Date().getTime()}`;
};

export const getQCViolinPlotUrl = (dataId: string): string => {
    if (!dataId) return "";
    return `${API_BASE_URL}/data/results/${dataId}/plot/qc_violin?t=${new Date().getTime()}`;
};

export const getProcessedDataUrl = (dataId: string): string => {
    if (!dataId) return "";
    return `${API_BASE_URL}/data/results/${dataId}/processed_data`; // No timestamp needed for download links usually
};

export const getMarkerGenesUrl = (dataId: string, clusterMethod: string, format: 'csv' | 'json'): string => {
    if (!dataId || !clusterMethod) return "";
     // Note: For JSON, we'll fetch it directly, this URL is primarily for the CSV download link
    return `${API_BASE_URL}/data/results/${dataId}/marker_genes/${clusterMethod}?format=${format}`;
};


// --- Result Data Fetching ---

export const getMarkerGenesData = async (dataId: string, clusterMethod: string): Promise<MarkerGene[]> => {
     if (!dataId || !clusterMethod) return Promise.reject("Missing dataId or clusterMethod");
     try {
        // Request JSON format from the endpoint
        const url = getMarkerGenesUrl(dataId, clusterMethod, 'json');
        const response = await apiClient.get(url); // apiClient uses the base URL
        return response.data as MarkerGene[];
    } catch (error) {
        console.error("Get marker genes data error:", error);
         if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to get marker gene data');
        }
        throw new Error('Failed to get marker gene data due to an unknown error');
    }
};

export const getGeneExpressionPlotData = async (dataId: string, geneName: string): Promise<GeneExpressionResponse> => {
     if (!dataId || !geneName) return Promise.reject("Missing dataId or geneName");
     try {
        const response = await apiClient.get(`/data/results/${dataId}/gene_expression/${encodeURIComponent(geneName)}`);
        return response.data as GeneExpressionResponse;
    } catch (error) {
        console.error(`Get gene expression data error for ${geneName}:`, error);
         if (axios.isAxiosError(error) && error.response) {
            // Provide more specific feedback for 404 (gene not found)
             if (error.response.status === 404) {
                 throw new Error(`Gene '${geneName}' not found or analysis results incomplete.`);
             }
            throw new Error(error.response.data.detail || 'Failed to get gene expression data');
        }
        throw new Error('Failed to get gene expression data due to an unknown error');
    }
};

// --- Integration Task ---
export const startIntegration = async (params: IntegrationParameters): Promise<TaskStartResponse> => {
  try {
      const response = await apiClient.post('/integration/start', params);
      return response.data;
  } catch (error) { 
    console.error("start integration data error:", error);
         if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to start integration data');
        }
        throw new Error('Failed to start integration data due to an unknown error');

   }
};

// getIntegrationTaskStatus can reuse getTaskStatus logic or have its own if needed
export const getIntegrationTaskStatus = getTaskStatus; // Reuse for now

// URLs for integration results
export const getIntegratedUmapPlotUrl = (integratedDataId: string, colorBy: 'batch' | 'clusters'): string => {
   if (!integratedDataId) return "";
   return `${API_BASE_URL}/integration/results/${integratedDataId}/plot/umap/${colorBy}?t=${new Date().getTime()}`;
};
export const getIntegratedDataUrl = (integratedDataId: string): string => {
   if (!integratedDataId) return "";
   return `${API_BASE_URL}/integration/results/${integratedDataId}/integrated_data`;
};


// --- Trajectory Task ---
export const startTrajectory = async (params: TrajectoryParameters): Promise<TaskStartResponse> => {
  try {
      const response = await apiClient.post('/trajectory/start', params);
      return response.data;
  } catch (error) { 
    
    console.error("start trajectory error:", error);
         if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to start trajectory');
        }
        throw new Error('Failed to start trajectory due to an unknown error');

   }
};
export const getTrajectoryTaskStatus = getTaskStatus; // Reuse for now

// URLs for trajectory results
export const getDiffmapPlotUrl = (sourceDataId: string): string => {
   if (!sourceDataId) return "";
   return `${API_BASE_URL}/trajectory/results/${sourceDataId}/plot/diffmap?t=${new Date().getTime()}`;
};
export const getPagaPlotUrl = (sourceDataId: string, plotType: 'graph' | 'umap_embedding'): string => {
   if (!sourceDataId) return "";
   return `${API_BASE_URL}/trajectory/results/${sourceDataId}/plot/paga/${plotType}?t=${new Date().getTime()}`;
};
export const getDptUmapPlotUrl = (sourceDataId: string): string => {
   if (!sourceDataId) return "";
   return `${API_BASE_URL}/trajectory/results/${sourceDataId}/plot/umap/dpt?t=${new Date().getTime()}`; // May 404 if not run
};


// --- Cell Communication Task ---
export const startCommunication = async (params: CellCommunicationParameters): Promise<TaskStartResponse> => {
  try {
      // NOTE: Do NOT send cellphonedb_database_path from frontend. Configure it server-side.
      // The backend task/API should retrieve this path from config/env variables.
      // We remove it here before sending.
      const { /* cellphonedb_database_path, */ ...paramsToSend } = params;
      const response = await apiClient.post('/communication/start', paramsToSend);
      return response.data;
  } catch (error) { 
    console.error("start communication error:", error);
         if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to start communication');
        }
        throw new Error('Failed to start communication due to an unknown error');
    
   }
};
export const getCommunicationTaskStatus = getTaskStatus; // Reuse for now

// URLs for communication results
export const getCellPhoneDbPlotUrl = (sourceDataId: string, plotName: string): string => {
   // plotName should match the file saved by the (optional) plotting in the task
   if (!sourceDataId || !plotName) return "";
   return `${API_BASE_URL}/communication/results/${sourceDataId}/plot/cellphonedb/${plotName}?t=${new Date().getTime()}`;
};
export const getCellPhoneDbDownloadUrl = (sourceDataId: string): string => {
   if (!sourceDataId) return "";
   return `${API_BASE_URL}/communication/results/${sourceDataId}/download/cellphonedb`;
};


// --- RNA Velocity Task ---
export const startVelocity = async (params: RnaVelocityParameters): Promise<TaskStartResponse> => {
    try {
        // source_data_id should be set correctly before calling this
        const response = await apiClient.post('/velocity/start', params);
        return response.data;
    } catch (error) {
        console.error("Start RNA velocity error:", error);
        if (axios.isAxiosError(error) && error.response) {
            // Handle 404 specifically if original file missing?
            if (error.response.status === 404 && error.response.data.detail?.includes("Original data file")) {
                 throw new Error("Original data file missing required spliced/unspliced layers. Cannot run RNA Velocity.");
            }
            throw new Error(error.response.data.detail || 'Failed to start RNA velocity analysis');
        }
        throw new Error('Failed to start RNA velocity analysis due to an unknown error');
     }
};

export const getVelocityTaskStatus = getTaskStatus; // Reuse main status checker

// --- URLs for Velocity Results ---
export const getVelocityPlotUrl = (sourceDataId: string, basis: string, type: 'grid' | 'stream'): string => {
    if (!sourceDataId || !basis) return "";
    const streamParam = type === 'stream';
    // The backend endpoint currently assumes 'umap' basis in the filename.
    // TODO: Make backend endpoint accept basis or use a more robust naming convention.
    // For now, we assume basis matches what was plotted (e.g., 'umap').
    console.warn("Velocity plot URL generation currently assumes basis matches plot filename on backend.");
    return `${API_BASE_URL}/velocity/results/${sourceDataId}/plot/velocity_embedding/${streamParam}?t=${new Date().getTime()}`;
};

export const getVelocityDataUrl = (sourceDataId: string): string => {
    if (!sourceDataId) return "";
    return `${API_BASE_URL}/velocity/results/${sourceDataId}/velocity_data`;
};

// --- ATAC Analysis Task ---
export const startAtacAnalysis = async (params: AtacAnalysisParameters): Promise<TaskStartResponse> => {
    try {
        // source_data_id should be set correctly before calling this
        const response = await apiClient.post('/atac/start', params);
        return response.data;
    } catch (error) {
        console.error("Start ATAC analysis error:", error);
        if (axios.isAxiosError(error) && error.response) {
            throw new Error(error.response.data.detail || 'Failed to start ATAC analysis');
        }
        throw new Error('Failed to start ATAC analysis due to an unknown error');
     }
};

export const getAtacTaskStatus = getTaskStatus; // Reuse main status checker

// --- URLs for ATAC Results ---
export const getAtacUmapPlotUrl = (sourceDataId: string, colorBy: string = 'clusters'): string => {
    if (!sourceDataId) return "";
    // Backend endpoint expects color_by in the URL path
    return `${API_BASE_URL}/atac/results/${sourceDataId}/plot/atac_umap?color_by=${encodeURIComponent(colorBy)}&t=${new Date().getTime()}`; // Pass color_by as query param or adjust endpoint
};

export const getAtacQcPlotUrl = (sourceDataId: string): string => {
    if (!sourceDataId) return "";
    return `${API_BASE_URL}/atac/results/${sourceDataId}/plot/atac_qc?t=${new Date().getTime()}`;
};

export const getProcessedAtacDataUrl = (sourceDataId: string): string => {
    if (!sourceDataId) return "";
    return `${API_BASE_URL}/atac/results/${sourceDataId}/processed_atac_data`;
};

// --- GRN Inference (DeepSEM) ---
export const inferGRN = async (
    expressionFile: File,
    networkFile: File | null,
    parameters: DeepSEMParameters
): Promise<GRNEdge[]> => {
    const formData = new FormData();
    formData.append('expression_file', expressionFile);
    if (networkFile) {
        formData.append('network_file', networkFile);
    }
    
    // Append all parameters as form fields
    Object.entries(parameters).forEach(([key, value]) => {
        formData.append(key, String(value));
    });

    try {
        const response = await apiClient.post('/deepsem/infer-grn/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 300000, // 5 minutes timeout for long-running inference
        });
        return response.data as GRNEdge[];
    } catch (error) {
        console.error("GRN inference error:", error);
        if (axios.isAxiosError(error)) {
            if (error.response) {
                // 服务器返回了响应，但有错误状态码
                const errorDetail = error.response.data?.detail || error.response.data?.message || error.response.statusText || 'GRN 推断失败';
                throw new Error(errorDetail);
            } else if (error.request) {
                // 请求已发出，但没有收到响应
                throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
            } else {
                // 请求配置出错
                throw new Error(error.message || '请求配置错误');
            }
        }
        throw new Error(error instanceof Error ? error.message : 'GRN 推断失败，未知错误');
    }
};

// --- GRN Inference (GRNBoost2/Genie3) ---
export const inferGRNWithGRNBoost2 = async (
    expressionFile: File,
    tfFile: File,
    algorithm: 'genie3' | 'grnboost2'
): Promise<GRNEdge[]> => {
    const formData = new FormData();
    formData.append('expression_file', expressionFile);
    formData.append('tf_file', tfFile);

    try {
        const response = await apiClient.post(`/grnboost2/infer-grn/${algorithm}`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 300000, // 5 minutes timeout for long-running inference
        });
        
        // GRNBoost2 返回的格式是 {TF, target, importance}，需要转换为 {source, target, weight}
        const data = response.data as Array<{TF: string, target: string, importance: number}>;
        return data.map(item => ({
            source: item.TF,
            target: item.target,
            weight: item.importance
        }));
    } catch (error) {
        console.error("GRNBoost2 inference error:", error);
        if (axios.isAxiosError(error)) {
            if (error.response) {
                const errorDetail = error.response.data?.detail || error.response.data?.message || error.response.statusText || 'GRN 推断失败';
                throw new Error(errorDetail);
            } else if (error.request) {
                throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
            } else {
                throw new Error(error.message || '请求配置错误');
            }
        }
        throw new Error(error instanceof Error ? error.message : 'GRN 推断失败，未知错误');
    }
};

// --- GRN Inference (CEFCON) ---
export const inferGRNWithCEFCON = async (
    expressionFile: File
): Promise<GRNEdge[]> => {
    const formData = new FormData();
    formData.append('expression_file', expressionFile);

    try {
        const response = await apiClient.post('/cefcon/infer-grn/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 3000000, // 50 minutes timeout for long-running inference
        });
        
        // CEFCON 返回的格式已经是 {source, target, weight}，直接返回
        return response.data as GRNEdge[];
    } catch (error) {
        console.error("CEFCON inference error:", error);
        if (axios.isAxiosError(error)) {
            if (error.response) {
                const errorDetail = error.response.data?.detail || error.response.data?.message || error.response.statusText || 'GRN 推断失败';
                throw new Error(errorDetail);
            } else if (error.request) {
                throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
            } else {
                throw new Error(error.message || '请求配置错误');
            }
        }
        throw new Error(error instanceof Error ? error.message : 'GRN 推断失败，未知错误');
    }
};

// --- GRN Inference (scDGRN) ---
export const inferGRNWithScDGRN = async (
    expressionZip: File
): Promise<Record<string, GRNEdge[]>> => {
    const formData = new FormData();
    formData.append('expression_zip', expressionZip);

    try {
        const response = await apiClient.post('/scdgrn/infer-grn-with-training/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 3000000, // 50 minutes timeout for long-running inference
        });
        
        // scDGRN 返回的格式是 {t1: [{TF, Target, score}], t2: [...], ...}
        // 需要转换为 {t1: [{source, target, weight}], t2: [...], ...}
        const result: Record<string, GRNEdge[]> = {};
        Object.keys(response.data).forEach(timePoint => {
            const data = response.data[timePoint] as Array<{TF: string | number, Target: string | number, score: number}>;
            result[timePoint] = data.map(item => ({
                source: String(item.TF),
                target: String(item.Target),
                weight: item.score
            }));
        });
        return result;
    } catch (error) {
        console.error("scDGRN inference error:", error);
        if (axios.isAxiosError(error)) {
            if (error.response) {
                const errorDetail = error.response.data?.detail || error.response.data?.message || error.response.statusText || 'GRN 推断失败';
                throw new Error(errorDetail);
            } else if (error.request) {
                throw new Error('无法连接到服务器，请检查网络连接或稍后重试');
            } else {
                throw new Error(error.message || '请求配置错误');
            }
        }
        throw new Error(error instanceof Error ? error.message : 'GRN 推断失败，未知错误');
    }
};