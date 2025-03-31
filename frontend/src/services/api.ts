import axios from 'axios';
import { UploadResponse, TaskStartResponse, TaskStatus, AnalysisParameters } from '../types';

// Adjust if your backend runs on a different port or host
const API_BASE_URL = 'http://211.87.232.159:8000/api'; // Point to the /api prefix

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await apiClient.post('/data/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    console.error("Upload error:", error);
    // Handle error appropriately, maybe re-throw or return a specific error object
    if (axios.isAxiosError(error) && error.response) {
        throw new Error(error.response.data.detail || 'File upload failed');
    }
    throw new Error('File upload failed due to an unknown error');
  }
};

export const startAnalysis = async (dataId: string, params: AnalysisParameters): Promise<TaskStartResponse> => {
    try {
        const response = await apiClient.post(`/analysis/analyze/${dataId}`, params);
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
        return response.data;
    } catch (error) {
        console.error("Get status error:", error);
         if (axios.isAxiosError(error) && error.response) {
            // Handle 404 for task not found differently?
            throw new Error(error.response.data.detail || 'Failed to get task status');
        }
        throw new Error('Failed to get task status due to an unknown error');
    }
};

// Function to get the URL for the result image
export const getUmapPlotUrl = (dataId: string): string => {
    // Returns the full URL the <img> tag can use directly
    return `${API_BASE_URL}/data/results/${dataId}/umap?t=${new Date().getTime()}`; // Add timestamp to prevent caching issues
};

// Add functions for other result types later
// export const getProcessedDataUrl = (dataId: string): string => {
//     return `${API_BASE_URL}/data/results/${dataId}/processed_data`;
// };