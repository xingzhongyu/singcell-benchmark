import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

// Child Components (Assume they exist in ./components/)
import MultiFileUpload from './components/MultiFileUpload';
import IntegrationConfig from './components/IntegrationConfig';
import DatasetSelector from './components/DatasetSelector';
import AnalysisRunner from './components/AnalysisRunner';
import ResultsViewer from './components/ResultsViewer';
import TaskProgress from './components/TaskProgress'; // General progress display

// API Service & Types
import {
    uploadFile, startAnalysis, startIntegration, startTrajectory, startCommunication,
    getTaskStatus // Use a single function now for checking status
} from './services/api';
import {
    AnalysisParameters, IntegrationParameters, TrajectoryParameters, CellCommunicationParameters,
    AppDatasetState, TaskStatus, AnalysisResultsSummary, IntegrationResultsSummary,
    TrajectoryResultsSummary, CellCommunicationResultsSummary, TaskStartResponse, UploadResponse, DatasetAnalysisState,
} from './types'; // Make sure all necessary types are exported from types/index.ts

// Default parameters (you might want to move these to a config file or constants)
// const defaultBasicParams: AnalysisParameters = { /* ... your defaults ... */ };
// Add default params for other analysis types if needed

type AnalysisType = 'basic' | 'integration' | 'trajectory' | 'communication'; // Use a type alias

function App() {
    const [datasets, setDatasets] = useState<Record<string, AppDatasetState>>({});
    const [selectedDataId, setSelectedDataId] = useState<string | null>(null);
    const [filesToUpload, setFilesToUpload] = useState<{ file: File, batchLabel: string, id: string }[]>([]);
    const [uploadProgress, setUploadProgress] = useState<Record<string, { status: 'pending' | 'uploading' | 'success' | 'error', message?: string }>>({});
    const [isUploading, setIsUploading] = useState<boolean>(false);
    const [globalError, setGlobalError] = useState<string | null>(null);

    // Use useRef for intervals to avoid dependency loops
    const intervalRef = useRef<Record<string, NodeJS.Timeout>>({});

    // --- Upload Logic ---
    const handleFilesPrepared = (preparedFiles: { file: File, batchLabel: string, id: string }[]) => {
        setFilesToUpload(preparedFiles);
        setUploadProgress(preparedFiles.reduce((acc, pf) => {
            acc[pf.id] = { status: 'pending' };
            return acc;
        }, {} as Record<string, { status: 'pending' | 'uploading' | 'success' | 'error', message?: string }>));
    };

    const handleConfirmUploads = async () => {
        if (filesToUpload.length === 0 || isUploading) return;
        setIsUploading(true);
        setGlobalError(null);

        const uploadPromises = filesToUpload.map(async (pf) => {
            try {
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'uploading' } }));
                const response = await uploadFile(pf.file);
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'success', message: `ID: ${response.data_id}` } }));
                // Add basic dataset state immediately after successful upload
                setDatasets(prev => ({
                    ...prev,
                    [response.data_id]: {
                        dataId: response.data_id,
                        filename: response.filename,
                        isIntegrated: false,
                        uploadTime: new Date().toISOString(),
                        // Initialize analysis states as undefined
                        basicAnalysis: undefined,
                        trajectoryAnalysis: undefined,
                        communicationAnalysis: undefined,
                    }
                }));
            } catch (error: any) {
                console.error(`Upload failed for ${pf.file.name}:`, error);
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'error', message: error.message || 'Upload failed' } }));
                setGlobalError(prev => `${prev ? prev + '\n' : ''}Upload failed for ${pf.file.name}: ${error.message}`);
            }
        });

        await Promise.all(uploadPromises);
        setIsUploading(false);
        setFilesToUpload([]); // Clear prepared files after attempting upload
    };

    // --- Polling Logic ---
    const stopPolling = useCallback((intervalKey: string) => {
        // console.log("Attempting to stop polling for:", intervalKey); // DEBUG
        if (intervalRef.current[intervalKey]) {
            // console.log("Clearing interval for:", intervalKey); // DEBUG
            clearInterval(intervalRef.current[intervalKey]);
            // Use functional update to safely modify the ref content
            intervalRef.current = { ...intervalRef.current }; // Create a shallow copy
            delete intervalRef.current[intervalKey]; // Delete the key
        } else {
             // console.log("No active interval found for:", intervalKey); // DEBUG
        }
    }, []); // No dependencies needed as it only interacts with the ref

    const pollTask = useCallback(async (dataId: string, analysisTypeKey: keyof AppDatasetState, taskId: string) => {
        const intervalKey = `${dataId}_${analysisTypeKey}_${taskId}`;
        // console.log(`Polling task ${intervalKey}...`); // DEBUG
        try {
            const statusResult = await getTaskStatus(taskId);

            // Check if task ID is still relevant for this dataset/analysis type
            let isStillRelevant = false;
            setDatasets(prevDatasets => {
                const currentDataset = prevDatasets[dataId];
                if (currentDataset && (currentDataset[analysisTypeKey] as DatasetAnalysisState)?.taskId === taskId) {
                    isStillRelevant = true;
                    const updatedAnalysisState = {
                        ...(currentDataset[analysisTypeKey] as DatasetAnalysisState),
                        status: statusResult,
                        resultsSummary: statusResult.status === 'SUCCESS' ? statusResult.result?.results_summary :( currentDataset[analysisTypeKey] as DatasetAnalysisState)?.resultsSummary,
                        error: statusResult.status === 'FAILURE' ? (statusResult.result?.details || statusResult.result?.error || 'Task Failed') : null
                    };
                    return {
                        ...prevDatasets,
                        [dataId]: {
                            ...currentDataset,
                            [analysisTypeKey]: updatedAnalysisState,
                        }
                    };
                }
                // If task ID or dataset changed, return previous state to avoid update
                return prevDatasets;
            });

             if (!isStillRelevant) {
                 console.warn(`Task ${taskId} is no longer relevant for ${dataId} -> ${analysisTypeKey}. Stopping polling.`);
                 stopPolling(intervalKey);
                 return; // Stop further processing
             }


            // Stop polling if task reached a final state
            if (statusResult.status === 'SUCCESS' || statusResult.status === 'FAILURE' || statusResult.status === 'REVOKED') {
                console.log(`Task ${taskId} (${dataId} -> ${analysisTypeKey}) finished with status: ${statusResult.status}. Stopping polling.`);
                stopPolling(intervalKey);
            }
        } catch (error: any) {
            console.error(`Error polling task status for ${intervalKey}:`, error);
            // Optionally update dataset state with polling error?
             setDatasets(prev => {
                 const current = prev[dataId];
                 if (current && (current[analysisTypeKey] as DatasetAnalysisState )?.taskId === taskId) {
                     return {
                         ...prev,
                         [dataId]: {
                             ...current,
                             [analysisTypeKey]: {
                                 ...(current[analysisTypeKey] as any), // Keep existing state
                                 error: `Polling Error: ${error.message}`,
                             }
                         }
                     }
                 }
                 return prev;
             })
            stopPolling(intervalKey); // Stop polling on error
        }
    }, [stopPolling]); // Depends only on stopPolling (stable)

    // --- Effect to Manage Polling Intervals ---
    useEffect(() => {
        // console.log("Polling effect running. Datasets:", datasets); // DEBUG
        const analysisTypeKeys: (keyof Omit<AppDatasetState, 'dataId' | 'filename' | 'isIntegrated' | 'uploadTime' | 'sourceDataIds'>)[] = [
            'basicAnalysis', 'integrationAnalysis', 'trajectoryAnalysis', 'communicationAnalysis'
        ];

        Object.entries(datasets).forEach(([dataId, datasetState]) => {
            analysisTypeKeys.forEach(analysisTypeKey => {
                const analysisState = datasetState[analysisTypeKey] as DatasetAnalysisState;

                if (analysisState?.taskId && analysisState.status &&
                    !['SUCCESS', 'FAILURE', 'REVOKED'].includes(analysisState.status.status))
                {
                    const intervalKey = `${dataId}_${analysisTypeKey}_${analysisState.taskId}`;
                    if (!intervalRef.current[intervalKey]) {
                        console.log(`Starting polling for ${intervalKey}`);
                        // Poll immediately, then set interval
                        pollTask(dataId, analysisTypeKey, analysisState.taskId);
                        const intervalId = setInterval(() => {
                            // Check inside interval if task is still relevant before polling
                             let isStillRelevant = false;
                             setDatasets(prev => { // Read latest state without causing loop
                                 const currentDs = prev[dataId];
                                 if (currentDs && (currentDs[analysisTypeKey] as DatasetAnalysisState)?.taskId === analysisState.taskId && !['SUCCESS', 'FAILURE', 'REVOKED'].includes((currentDs[analysisTypeKey] as DatasetAnalysisState)?.status?.status ?? '')) {
                                     isStillRelevant = true;
                                 }
                                 return prev;
                             });
                             if (isStillRelevant) {
                                pollTask(dataId, analysisTypeKey, analysisState.taskId!);
                             } else {
                                console.log(`Polling check: Task ${analysisState.taskId} no longer relevant or finished. Stopping interval ${intervalKey}.`);
                                stopPolling(intervalKey); // Stop if status changed between checks
                             }

                        }, 7000); // Poll every 7 seconds
                        // Use functional update to safely modify ref without loop
                         intervalRef.current = { ...intervalRef.current, [intervalKey]: intervalId };
                    }
                }
                 // Cleanup check: Stop polling if task somehow finished but interval remains
                 else if (analysisState?.taskId) {
                    const intervalKey = `${dataId}_${analysisTypeKey}_${analysisState.taskId}`;
                    if (intervalRef.current[intervalKey] && analysisState.status && ['SUCCESS', 'FAILURE', 'REVOKED'].includes(analysisState.status.status)) {
                         console.warn(`Stopping orphaned polling interval ${intervalKey} due to final task status.`);
                         stopPolling(intervalKey);
                     }
                 }
            });
        });

        // Cleanup function to clear all intervals on component unmount or if datasets change drastically
        return () => {
            console.log("Cleaning up all polling intervals...");
            Object.values(intervalRef.current).forEach(clearInterval);
            intervalRef.current = {}; // Reset ref
        };
    // Depend only on datasets structure (keys and task IDs/status) and the stable pollTask function
    // Using JSON.stringify is a common way to track deep changes, but can be inefficient.
    // A more targeted dependency array might be better if performance is critical.
    // For now, this ensures the effect runs when tasks are added/removed/finish.
    }, [datasets, pollTask, stopPolling]);


    // --- Selecting Dataset ---
    const handleDatasetSelect = (id: string | null) => setSelectedDataId(id);

    // --- Running Analyses on Selected Dataset ---
    const handleRunAnalysis = async (
        analysisType: 'basic' | 'trajectory' | 'communication', // Integration handled separately
        params: any // AnalysisParameters | TrajectoryParameters | CellCommunicationParameters
    ) => {
        if (!selectedDataId) {
            setGlobalError("No dataset selected to run analysis on.");
            return;
        }
        setGlobalError(null); // Clear previous errors

        const analysisTypeKey = `${analysisType}Analysis` as keyof AppDatasetState; // e.g., 'basicAnalysis'

        // Start loading state specifically for this analysis
         setDatasets(prev => ({
            ...prev,
            [selectedDataId]: {
                ...prev[selectedDataId],
                [analysisTypeKey]: { // Reset previous state for this analysis type
                    taskId: null,
                    status: { task_id: '', status: 'PENDING', result: { status: 'Submitting task...'}}, // Initial 'PENDING' like status
                    parameters: params, // Store params used
                    resultsSummary: null,
                    error: null,
                 }
            }
         }))


        try {
            let response: TaskStartResponse;
            if (analysisType === 'basic') {
                response = await startAnalysis(selectedDataId, params as AnalysisParameters);
            } else if (analysisType === 'trajectory') {
                // Ensure source_data_id is set correctly
                const trajectoryParams = { ...(params as TrajectoryParameters), source_data_id: selectedDataId };
                response = await startTrajectory(trajectoryParams);
            } else if (analysisType === 'communication') {
                // Ensure source_data_id is set correctly
                const communicationParams = { ...(params as CellCommunicationParameters), source_data_id: selectedDataId };
                response = await startCommunication(communicationParams);
            } else {
                throw new Error("Invalid analysis type");
            }

            // Update state with the actual task ID and PENDING status
            setDatasets(prev => ({
                ...prev,
                [selectedDataId]: {
                    ...prev[selectedDataId],
                    [analysisTypeKey]: {
                        ...(prev[selectedDataId][analysisTypeKey] as any), // Keep params
                        taskId: response.task_id,
                        status: { task_id: response.task_id, status: 'PENDING', result: null },
                    }
                }
            }));
             // Polling will be started by the useEffect hook reacting to the state change

        } catch (error: any) {
            console.error(`Failed to start ${analysisType} analysis:`, error);
            setGlobalError(`Failed to start ${analysisType} analysis: ${error.message}`);
             // Update state to reflect failure to start
             setDatasets(prev => ({
                ...prev,
                [selectedDataId]: {
                    ...prev[selectedDataId],
                    [analysisTypeKey]: {
                        ...(prev[selectedDataId][analysisTypeKey] as any), // Keep params
                        taskId: null,
                        status: null, // Clear status
                        error: `Failed to start task: ${error.message}`
                    }
                }
            }));
        }
    };


    // --- Integration Logic ---
    const handleStartIntegration = async (integrationParams: IntegrationParameters) => {
        setGlobalError(null);
        const outputDataId = integrationParams.output_data_id || `integrated_${Date.now()}`; // Generate temp ID

         // Add placeholder for integrated dataset
         setDatasets(prev => ({
            ...prev,
            [outputDataId]: {
                dataId: outputDataId,
                isIntegrated: true,
                sourceDataIds: integrationParams.files.map(f => f.data_id),
                uploadTime: new Date().toISOString(),
                // Set up integrationAnalysis state
                integrationAnalysis: {
                    taskId: null,
                    status: { task_id: '', status: 'PENDING', result: { status: 'Submitting task...'}},
                    parameters: integrationParams,
                    resultsSummary: null,
                    error: null,
                 }
            }
         }));

        try {
            const response = await startIntegration({ ...integrationParams, output_data_id: outputDataId }); // Send ID to backend

            // Update placeholder with actual task ID
            setDatasets(prev => {
                const current = prev[outputDataId];
                if(current?.integrationAnalysis) { // Check if still exists
                    return {
                        ...prev,
                        [outputDataId]: {
                            ...current,
                            integrationAnalysis: {
                                ...current.integrationAnalysis,
                                taskId: response.task_id,
                                status: { task_id: response.task_id, status: 'PENDING', result: null },
                            }
                        }
                    }
                }
                return prev; // No change if dataset disappeared
            });
            // Polling will start via useEffect

        } catch (error: any) {
            console.error('Failed to start integration analysis:', error);
            setGlobalError(`Failed to start integration analysis: ${error.message}`);
             // Update placeholder state to show error
             setDatasets(prev => {
                 const current = prev[outputDataId];
                 if (current?.integrationAnalysis) {
                     return {
                         ...prev,
                         [outputDataId]: {
                             ...current,
                             integrationAnalysis: {
                                 ...current.integrationAnalysis,
                                 taskId: null,
                                 status: null,
                                 error: `Failed to start task: ${error.message}`
                             }
                         }
                     };
                 }
                 return prev; // No change
             });
        }
    };


    const selectedDataset = selectedDataId ? datasets[selectedDataId] : null;
    // Filter out datasets that are currently being integrated (have placeholder state but no task success yet)
    const selectableDatasets = Object.values(datasets).filter(ds =>
        !(ds.isIntegrated && (!ds.integrationAnalysis || ds.integrationAnalysis.status?.status !== 'SUCCESS'))
    ).reduce((acc, ds) => {
         acc[ds.dataId] = ds; // Convert back to record for selector
         return acc;
     }, {} as Record<string, AppDatasetState>);


    return (
        <div className="App">
            <header className="App-header">
                <h1>Scanpy Web Analysis App</h1>
            </header>
            <main>
                {globalError && <p className="global-error">Error: {globalError}</p>}

                {/* --- Section 1: Data Input & Integration --- */}
                <section className="app-section">
                    <h3>1. Upload & Integrate Data</h3>
                    <MultiFileUpload
                        onFilesPrepared={handleFilesPrepared}
                        uploadProgress={uploadProgress}
                        isUploading={isUploading}
                    />
                    <button onClick={handleConfirmUploads} disabled={filesToUpload.length === 0 || isUploading}>
                        {isUploading ? 'Uploading...' : `Upload ${filesToUpload.length} File(s)`}
                    </button>

                    <IntegrationConfig
                        availableDatasets={Object.values(datasets).filter(d => !d.isIntegrated)} // Pass original uploads
                        onStartIntegration={handleStartIntegration}
                        // Find if any integration task is running/pending for display
                        activeIntegrationTask={Object.values(datasets).find(d => d.isIntegrated && d.integrationAnalysis && !['SUCCESS', 'FAILURE'].includes(d.integrationAnalysis.status?.status ?? ''))?.integrationAnalysis}
                    />
                </section>

                {/* --- Section 2: Select Dataset & Run Analyses --- */}
                 {/* Only show if there are selectable datasets */}
                 {Object.keys(selectableDatasets).length > 0 && (
                    <section className="app-section">
                        <hr />
                        <h3>2. Select Dataset & Analyze</h3>
                        <DatasetSelector
                            datasets={selectableDatasets}
                            onSelect={handleDatasetSelect}
                            selectedId={selectedDataId}
                        />

                        {selectedDataset && (
                            <AnalysisRunner
                                dataset={selectedDataset}
                                onRunAnalysis={handleRunAnalysis}
                            />
                        )}
                    </section>
                 )}

                {/* --- Section 3: View Results --- */}
                {selectedDataset && (
                    <section className="app-section">
                        <hr />
                        <h3>3. Results for Dataset: {selectedDataset.filename || selectedDataId} {selectedDataset.isIntegrated ? '(Integrated)' : ''}</h3>
                        <ResultsViewer dataset={selectedDataset} />
                    </section>
                )}
                 {/* Show message if no datasets are available */}
                 {Object.keys(datasets).length === 0 && !isUploading && filesToUpload.length === 0 && (
                     <p>Upload one or more .h5ad files to begin.</p>
                 )}

            </main>
        </div>
    );
}
export default App;