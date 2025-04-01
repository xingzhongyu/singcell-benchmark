// frontend/src/services/api.ts
import axios from 'axios';
import {
    UploadResponse, TaskStartResponse, TaskStatus, AnalysisParameters,
    MarkerGene, GeneExpressionResponse,
    IntegrationParameters, TrajectoryParameters, CellCommunicationParameters,
    IntegrationResultsSummary, TrajectoryResultsSummary, CellCommunicationResultsSummary, AppDatasetState // Add AppDatasetState if used for complex state
} from '../types';

// Adjust if your backend runs on a different port or host
// Use environment variables in a real app: process.env.REACT_APP_API_URL || 'http://localhost:8000/api'
const API_BASE_URL = 'http://211.87.232.159:8000/api'; // Your backend API base URL

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