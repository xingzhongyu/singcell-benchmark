// frontend/src/App.tsx
import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import FileUpload from './components/FileUpload'; // Assuming you have this
import ResultDisplay from './components/ResultDisplay'; // Assuming you have this
import TaskProgress from './components/TaskProgress'; // New component suggestion
import ParameterTabs from './components/ParameterTabs'; // New component suggestion
import { uploadFile, startAnalysis, getTaskStatus } from './services/api';
import { AnalysisParameters, TaskStatus, AnalysisResultsSummary } from './types';

const defaultParams: AnalysisParameters = {
    mito_prefix: 'MT-',
    min_genes_after_qc: 200,
    min_cells_after_qc: 3,
    select_hvgs: true,
    hvg_min_mean: 0.0125,
    hvg_max_mean: 3,
    hvg_min_disp: 0.5,
    hvg_n_top_genes: null, // Default to using mean/dispersion
    normalize_target_sum: 10000,
    pca_n_comps: 50,
    neighbors_n_pcs: 30,
    neighbors_n_neighbors: 15,
    umap_min_dist: 0.5,
    umap_spread: 1.0,
    clustering_method: 'leiden',
    leiden_resolution: 0.5,
    louvain_resolution: 0.5,
    marker_gene_method: 'wilcoxon',
    marker_gene_n_genes: 25,
};

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dataId, setDataId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisParams, setAnalysisParams] = useState<AnalysisParameters>(defaultParams);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResultsSummary | null>(null);

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    // Reset previous results when a new file is selected
    setDataId(null);
    setTaskId(null);
    setTaskStatus(null);
    setError(null);
    setAnalysisResults(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await uploadFile(selectedFile);
      setDataId(response.data_id);
      console.log('Upload successful:', response);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
      setDataId(null); // Ensure dataId is null on failure
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartAnalysis = async () => {
    if (!dataId) return;
    setIsLoading(true);
    setError(null);
    setTaskId(null); // Reset task ID before starting new one
    setTaskStatus(null);
    setAnalysisResults(null); // Clear previous results display
    try {
      // Pass the current analysisParams state
      const response = await startAnalysis(dataId, analysisParams);
      setTaskId(response.task_id);
      setTaskStatus({ task_id: response.task_id, status: 'PENDING', result: null }); // Initial status
      console.log('Analysis started:', response);
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const pollTaskStatus = useCallback(async () => {
    // Ensure taskId exists before proceeding
    if (!taskId || !dataId) {
        console.log(`[${new Date().toLocaleTimeString()}] pollTaskStatus: Aborting, missing taskId or dataId.`);
        // Consider clearing interval here if taskId becomes null unexpectedly
        // This might require taskId to be a dependency of useEffect
        return;
    };

    console.log(`[${new Date().toLocaleTimeString()}] Polling status for task ${taskId}...`);
    let statusResult: TaskStatus | null = null; // Define variable outside try

    try {
        statusResult = await getTaskStatus(taskId); // Fetch status
        console.log(`[${new Date().toLocaleTimeString()}] Fetched status for ${taskId}:`, statusResult);

        // --- Task ID Check ---
        // Ensure the status received is for the task we are currently tracking
        if (statusResult.task_id !== taskId) {
            console.warn(`[${new Date().toLocaleTimeString()}] Task ID mismatch. Current: ${taskId}, Fetched: ${statusResult.task_id}. Ignoring status.`);
            return; // Stop processing this status update
        }

        // --- Update State (Always update state with the latest fetched status) ---
        setTaskStatus(statusResult);

        // --- !! ACT ON FINAL STATUS IMMEDIATELY !! ---
        // Check the *fetched* statusResult directly, don't wait for the next render's taskStatus state
        if (statusResult.status === 'SUCCESS') {
            console.log(`[${new Date().toLocaleTimeString()}] SUCCESS state detected for ${taskId}. Processing result.`);
            if (statusResult.result?.status === 'Complete') {
                // Ensure the result structure is as expected
                setAnalysisResults(statusResult.result.results_summary as AnalysisResultsSummary);
                setError(null); // Clear any previous errors
                console.log(`[${new Date().toLocaleTimeString()}] Analysis results set.`);
            } else {
                // Handle unexpected SUCCESS result format
                console.error(`[${new Date().toLocaleTimeString()}] SUCCESS state for ${taskId} but unexpected result format:`, statusResult.result);
                setError(`Analysis finished but result data is missing or malformed.`);
                setAnalysisResults(null);
            }
            // No need to return here, useEffect will stop the interval on next render

        } else if (statusResult.status === 'FAILURE') {
            console.log(`[${new Date().toLocaleTimeString()}] FAILURE state detected for ${taskId}. Setting error message.`);
            const failureResult = statusResult.result as any; // Cast for easier access
            const errorDetails = failureResult?.error ? ` (${failureResult.error})` : '';
            // Limit traceback length if necessary
            const tracebackInfo = failureResult?.traceback ? `\nTraceback available (see console)` : '';
            if (failureResult?.traceback) console.error("Failure Traceback:", failureResult.traceback); // Log full traceback

            setError(`Analysis task failed${errorDetails}${tracebackInfo}`);
            setAnalysisResults(null);
            // No need to return here, useEffect will stop the interval on next render
        }
        // No 'else' needed - if it's PENDING/PROGRESS/STARTED, state is updated, and useEffect will continue the interval

    } catch (err: any) {
        // Handle errors during the API call itself
        console.error(`[${new Date().toLocaleTimeString()}] Error polling task status for ${taskId}:`, err);
        setError(`Error checking task status: ${err.message}. Polling may stop.`);
        // Optionally stop polling by clearing taskId, which useEffect depends on
        // setTaskId(null);
    }

    // No explicit return needed unless aborting early (like task ID mismatch)

    // Dependencies: taskId and dataId are crucial.
    // setTaskStatus, setAnalysisResults, setError are stable state setters from useState.
}, [taskId, dataId, setTaskStatus, setAnalysisResults, setError]); // Removed taskStatus dependency


  // useEffect remains largely the same, it just controls the *timing* of the polling
  useEffect(() => {
      let intervalId: NodeJS.Timeout | null = null;
      console.log(`[${new Date().toLocaleTimeString()}] useEffect triggered. Task ID: ${taskId}, Status: ${taskStatus?.status}`);

      // Start polling ONLY if we have a task ID AND the status is NOT final
      if (taskId && taskStatus?.status !== 'SUCCESS' && taskStatus?.status !== 'FAILURE') {
          console.log(`[${new Date().toLocaleTimeString()}] useEffect: Setting up interval for ${taskId}. Current status: ${taskStatus?.status}`);

          // Optional: Poll immediately once when starting interval?
          // Be careful not to cause rapid polling if state updates quickly.
          // pollTaskStatus();

          intervalId = setInterval(pollTaskStatus, 5000); // Poll every 5 seconds
      } else {
          console.log(`[${new Date().toLocaleTimeString()}] useEffect: NOT setting up interval. Task ID: ${taskId}, Status: ${taskStatus?.status}`);
      }

      // Cleanup function: Clears interval when taskId changes, status becomes final, or component unmounts
      return () => {
          console.log(`[${new Date().toLocaleTimeString()}] useEffect CLEANUP running. Clearing interval ${intervalId} for task ${taskId}.`);
          if (intervalId) {
              clearInterval(intervalId);
          }
      };
      // Dependencies: Listen to taskId and taskStatus.status to decide *whether* to poll.
      // pollTaskStatus is included because it's used inside the effect.
  }, [taskId, taskStatus?.status, pollTaskStatus]);


  // Handler to update parameters from child components
  const handleParamsChange = (newParams: Partial<AnalysisParameters>) => {
      setAnalysisParams(prevParams => ({ ...prevParams, ...newParams }));
  };


  return (
    <div className="App">
      <header className="App-header">
        <h1>Scanpy Web Analysis</h1>
      </header>

      <main>
        {/* --- Step 1: Upload --- */}
        <section>
          <h3>1. Upload Data</h3>
          <FileUpload onFileSelect={handleFileSelect} currentFile={selectedFile} />
          <button onClick={handleUpload} disabled={!selectedFile || isLoading}>
            {isLoading && !dataId ? 'Uploading...' : 'Upload .h5ad File'}
          </button>
          {dataId && !taskId && <p style={{ color: 'green' }}>File uploaded successfully! Data ID: {dataId}</p>}
        </section>

        {error && <p style={{ color: 'red', whiteSpace: 'pre-wrap' }}>Error: {error}</p>}

        {/* --- Step 2: Configure & Run Analysis --- */}
        {dataId && (
          <section>
            <hr />
            <h3>2. Configure & Run Analysis</h3>
             {/* Use Tabs or Accordion for better organization */}
            <ParameterTabs params={analysisParams} onParamsChange={handleParamsChange} />

            <button onClick={handleStartAnalysis} disabled={!dataId || isLoading || (!!taskId && taskStatus?.status !== 'SUCCESS' && taskStatus?.status !== 'FAILURE')}>
              {isLoading && !!taskId ? 'Processing...' : 'Start Analysis'}
            </button>
          </section>
        )}

        {/* --- Step 3: View Progress & Results --- */}
        {taskId && dataId && (
             <section>
                 <hr />
                 <h3>3. Analysis Progress & Results</h3>
                 <TaskProgress status={taskStatus} />
                 {/* Conditionally render ResultDisplay only when SUCCESS */}
                 {taskStatus?.status === 'SUCCESS' && analysisResults && (
                     <ResultDisplay
                         dataId={dataId}
                         resultsSummary={analysisResults} // Pass the detailed results summary
                         clusterMethod={analysisParams.clustering_method} // Pass method used
                     />
                 )}
             </section>
        )}

      </main>
    </div>
  );
}

export default App;