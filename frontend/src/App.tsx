import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import ResultDisplay from './components/ResultDisplay';
import { startAnalysis, getTaskStatus } from './services/api';
import { UploadResponse, TaskStatus, AnalysisParameters } from './types';

function App() {
  const [uploadInfo, setUploadInfo] = useState<UploadResponse | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [analysisParams, setAnalysisParams] = useState<AnalysisParameters>({
    // Default parameters - Make these configurable via UI later
    min_genes: 200,
    min_cells: 3,
    pca_n_comps: 50,
    neighbors_n_pcs: 30,
    leiden_resolution: 0.5,
  });
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleUploadSuccess = (response: UploadResponse) => {
    setUploadInfo(response);
    // Reset previous analysis state
    setTaskId(null);
    setTaskStatus(null);
    setError(null);
  };

  const handleRunAnalysis = async () => {
    if (!uploadInfo) {
      setError("Please upload a file first.");
      return;
    }
    setError(null);
    setTaskId(null); // Reset task ID for new run
    setTaskStatus(null);

    try {
      const response = await startAnalysis(uploadInfo.data_id, analysisParams);
      setTaskId(response.task_id);
      setTaskStatus({ task_id: response.task_id, status: 'PENDING' }); // Initial status
      setIsPolling(true); // Start polling
    } catch (err: any) {
      setError(err.message || "Failed to start analysis.");
      console.error(err);
      setIsPolling(false);
    }
  };

  // --- Status Polling Logic ---
  const pollStatus = useCallback(async () => {
    if (!taskId || !isPolling) return;

    try {
        const statusResult = await getTaskStatus(taskId);
        setTaskStatus(statusResult);

        // Stop polling if task is finished or failed
        if (statusResult.status === 'SUCCESS' || statusResult.status === 'FAILURE') {
            setIsPolling(false);
            if (statusResult.status === 'FAILURE') {
                 setError(`Analysis failed: ${JSON.stringify(statusResult.result?.details || statusResult.result || 'Unknown error')}`);
            }
        }
    } catch (err: any) {
        setError(err.message || "Failed to get task status.");
        console.error("Polling error:", err);
        setIsPolling(false); // Stop polling on error
    }
}, [taskId, isPolling]);


  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    if (isPolling && taskId) {
      // Poll immediately first time
      pollStatus();
      // Then set interval
      intervalId = setInterval(pollStatus, 3000); // Poll every 3 seconds
    }

    // Cleanup function to clear interval when component unmounts or polling stops
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isPolling, taskId, pollStatus]); // Rerun effect if isPolling or taskId changes


  // --- Parameter Handling (Basic Example) ---
  const handleParamChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      const { name, value, type } = event.target;
      const parsedValue = type === 'number' ? parseFloat(value) : value;
      setAnalysisParams(prevParams => ({
          ...prevParams,
          [name]: parsedValue,
      }));
  };


  return (
    <div className="App">
      <header className="App-header">
        <h1>Scanpy Web App</h1>
      </header>
      <main>
        <FileUpload onUploadSuccess={handleUploadSuccess} />

        <hr />

        {uploadInfo && (
            <div>
                <h3>2. Run Analysis</h3>
                 {/* Basic Parameter Inputs - Enhance this into a proper form */}
                 <div>
                    <label>Min Genes: </label>
                    <input type="number" name="min_genes" value={analysisParams.min_genes} onChange={handleParamChange} />
                 </div>
                 <div>
                    <label>Min Cells: </label>
                    <input type="number" name="min_cells" value={analysisParams.min_cells} onChange={handleParamChange} />
                 </div>
                 <div>
                    <label>PCA Components: </label>
                    <input type="number" name="pca_n_comps" value={analysisParams.pca_n_comps} onChange={handleParamChange} />
                 </div>
                 <div>
                    <label>Neighbors PCs: </label>
                    <input type="number" name="neighbors_n_pcs" value={analysisParams.neighbors_n_pcs} onChange={handleParamChange} />
                 </div>
                 <div>
                    <label>Leiden Resolution: </label>
                    <input type="number" step="0.1" name="leiden_resolution" value={analysisParams.leiden_resolution} onChange={handleParamChange} />
                 </div>
                 <br/>
                <button onClick={handleRunAnalysis} disabled={!uploadInfo || isPolling || (taskStatus?.status === 'SUCCESS')}>
                  {isPolling ? 'Analysis Running...' : (taskStatus?.status === 'SUCCESS' ? 'Analysis Complete' : 'Run Analysis')}
                </button>

                 {taskStatus && (
                    <div style={{marginTop: '10px'}}>
                        <p>Task ID: {taskStatus.task_id}</p>
                        <p>Status: <strong>{taskStatus.status}</strong></p>
                        {taskStatus.status === 'PROGRESS' && taskStatus.result?.status && (
                            <p>Details: {taskStatus.result.status}</p>
                        )}
                        {/* Display final result message or error */}
                         {taskStatus.status === 'SUCCESS' && taskStatus.result?.status && (
                            <p style={{color: 'green'}}>Details: {taskStatus.result.status}</p>
                        )}
                         {taskStatus.status === 'FAILURE' && (
                            <p style={{color: 'red'}}>Failed: {JSON.stringify(taskStatus.result?.details || taskStatus.result)}</p>
                        )}
                    </div>
                )}
                {error && <p style={{ color: 'red', marginTop: '10px' }}>Error: {error}</p>}
            </div>
        )}

        <hr />

        <ResultDisplay
          dataId={uploadInfo?.data_id ?? null}
          analysisComplete={taskStatus?.status === 'SUCCESS'}
        />

      </main>
    </div>
  );
}

export default App;