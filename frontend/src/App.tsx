import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

// Child Components
import MultiFileUpload from './components/MultiFileUpload';
import IntegrationConfig from './components/IntegrationConfig';
import DatasetSelector from './components/DatasetSelector';
import AnalysisRunner from './components/AnalysisRunner';
import ResultsViewer from './components/ResultsViewer';
import TaskProgress from './components/TaskProgress';
import Sidebar from './components/Sidebar'; // <<< 1. 引入侧边栏组件
import GRNInference from './components/GRNInference'; // <<< 添加 GRN 推断组件
import './components/Sidebar.css';      // <<< 2. 引入侧边栏样式 (如果还没在 Sidebar.tsx 中引入)
// API Service & Types
import {
    uploadFile, startAnalysis, startIntegration, startTrajectory, startCommunication, startVelocity, // Added startVelocity
    getTaskStatus,
    startAtacAnalysis
} from './services/api';
import {
    AnalysisParameters, IntegrationParameters, TrajectoryParameters, CellCommunicationParameters, RnaVelocityParameters, // Added RnaVelocityParameters
    AppDatasetState, TaskStatus, AnalysisResultsSummary, IntegrationResultsSummary,
    TrajectoryResultsSummary, CellCommunicationResultsSummary, RnaVelocityResultsSummary, // Added RnaVelocityResultsSummary
    TaskStartResponse, UploadResponse, DatasetAnalysisState, AtacAnalysisParameters,
} from './types';

// Define AnalysisType alias including 'velocity'
type AnalysisType = 'basic' | 'integration' | 'trajectory' | 'communication' | 'velocity'|'atac';

// Define default parameters (condense imports or move to separate file)
const defaultBasicParams: AnalysisParameters = { mito_prefix: 'MT-', min_genes_after_qc: 200, min_cells_after_qc: 3, select_hvgs: true, hvg_min_mean: 0.0125, hvg_max_mean: 3, hvg_min_disp: 0.5, hvg_n_top_genes: null, normalize_target_sum: 10000, pca_n_comps: 50, neighbors_n_pcs: 30, neighbors_n_neighbors: 15, umap_min_dist: 0.5, umap_spread: 1.0, clustering_method: 'leiden', leiden_resolution: 0.5, louvain_resolution: 0.5, marker_gene_method: 'wilcoxon', marker_gene_n_genes: 25 };
const defaultTrajectoryParams: Omit<TrajectoryParameters, 'source_data_id'> = { run_diffmap: true, diffmap_n_comps: 15, run_paga: true, paga_clustering_key: "clusters", paga_threshold_connectivities: 0.05, paga_threshold_confidence: 0.01, calculate_dpt: true, dpt_root_cluster: null };
const defaultCommunicationParams: Omit<CellCommunicationParameters, 'source_data_id'> = { clustering_key: "clusters", counts_layer: null, gene_id_column: null, output_path_suffix: "cellphonedb_out", threads: 4, subsampling: false, subsampling_num_pc: 100, subsampling_log: false };
const defaultVelocityParams: Omit<RnaVelocityParameters, 'source_data_id'> = { mode: 'stochastic', fit_basal_transcription: true, vgraph_n_neighbors: null, vgraph_approx: null, embedding_basis: 'umap', color_key: 'clusters', save_updated_adata: false };
const defaultAtacParams: Omit<AtacAnalysisParameters, 'source_data_id'> = { // <<< ADD THIS
    qc_min_counts: 1000, qc_max_counts_quantile: 0.99, qc_min_features_by_counts: 500,
    tfidf_transform: true, tfidf_scale_factor: null, lsi_n_components: 50, lsi_use_highly_variable: false,
    neighbors_n_pcs: 30, neighbors_n_neighbors: 15, run_umap: true, umap_min_dist: 0.5, umap_spread: 1.0,
    run_clustering: true, clustering_resolution: 0.5, save_processed_adata: true
};

function App() {
    const [activePage, setActivePage] = useState<'preprocessing' | 'grn'>('preprocessing');
    const [datasets, setDatasets] = useState<Record<string, AppDatasetState>>({});
    const [selectedDataId, setSelectedDataId] = useState<string | null>(null);
    const [filesToUpload, setFilesToUpload] = useState<{ file: File, batchLabel: string, id: string }[]>([]);
    const [uploadProgress, setUploadProgress] = useState<Record<string, { status: 'pending' | 'uploading' | 'success' | 'error', message?: string }>>({});
    const [isUploading, setIsUploading] = useState<boolean>(false);
    const [globalError, setGlobalError] = useState<string | null>(null);
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
        const successfulUploads: Record<string, AppDatasetState> = {};

        const uploadPromises = filesToUpload.map(async (pf) => {
            try {
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'uploading' } }));
                const response = await uploadFile(pf.file);
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'success', message: `ID: ${response.data_id}` } }));
                // Prepare dataset state entry
                successfulUploads[response.data_id] = {
                    dataId: response.data_id,
                    filename: response.filename,
                    batchLabel: pf.batchLabel, // Store the batch label
                    isIntegrated: false,
                    uploadTime: new Date().toISOString(),
                    basicAnalysis: undefined,
                    trajectoryAnalysis: undefined,
                    communicationAnalysis: undefined,
                    velocityAnalysis: undefined, // Initialize velocity state
                    atacAnalysis: undefined, // <<< ADD THIS INITIALIZATION
                };
            } catch (error: any) {
                console.error(`Upload failed for ${pf.file.name}:`, error);
                setUploadProgress(prev => ({ ...prev, [pf.id]: { status: 'error', message: error.message || 'Upload failed' } }));
                setGlobalError(prev => `${prev ? prev + '\n' : ''}Upload failed for ${pf.file.name}: ${error.message}`);
            }
        });

        await Promise.all(uploadPromises);
        // Add successfully uploaded datasets to the main state
        if (Object.keys(successfulUploads).length > 0) {
             setDatasets(prev => ({ ...prev, ...successfulUploads }));
        }
        setIsUploading(false);
        setFilesToUpload([]);
    };

    // --- Polling Logic (Stable) ---
    const stopPolling = useCallback((intervalKey: string) => {
        if (intervalRef.current[intervalKey]) {
            clearInterval(intervalRef.current[intervalKey]);
            intervalRef.current = { ...intervalRef.current };
            delete intervalRef.current[intervalKey];
        }
    }, []);

    const pollTask = useCallback(async (dataId: string, analysisTypeKey: keyof AppDatasetState, taskId: string) => {
        const intervalKey = `${dataId}_${analysisTypeKey}_${taskId}`;
        try {
            const statusResult = await getTaskStatus(taskId);
            let isStillRelevant = false;
            setDatasets(prevDatasets => {
                const currentDataset = prevDatasets[dataId];
                if (currentDataset && (currentDataset[analysisTypeKey] as DatasetAnalysisState)?.taskId === taskId) {
                    isStillRelevant = true;
                    const updatedAnalysisState = {
                        ...(currentDataset[analysisTypeKey] as DatasetAnalysisState),
                        status: statusResult,
                        resultsSummary: statusResult.status === 'SUCCESS' ? statusResult.result?.results_summary : (currentDataset[analysisTypeKey] as DatasetAnalysisState)?.resultsSummary,
                        error: statusResult.status === 'FAILURE' ? (statusResult.result?.details || statusResult.result?.error || 'Task Failed') : null
                    };
                    return { ...prevDatasets, [dataId]: { ...currentDataset, [analysisTypeKey]: updatedAnalysisState } };
                }
                return prevDatasets;
            });
             if (!isStillRelevant) {
                 console.warn(`Task ${taskId} no longer relevant for ${dataId} -> ${analysisTypeKey}. Stopping polling.`);
                 stopPolling(intervalKey);
                 return;
             }
            if (statusResult.status === 'SUCCESS' || statusResult.status === 'FAILURE' || statusResult.status === 'REVOKED') {
                stopPolling(intervalKey);
            }
        } catch (error: any) {
            console.error(`Error polling task status for ${intervalKey}:`, error);
             setDatasets(prev => { /* Update error state safely */
                const current = prev[dataId];
                 if (current && (current[analysisTypeKey] as DatasetAnalysisState)?.taskId === taskId) {
                     return {...prev, [dataId]: {...current, [analysisTypeKey]: {...(current[analysisTypeKey] as any), error: `Polling Error: ${error.message}`}}};
                 } return prev;
             });
            stopPolling(intervalKey);
        }
    }, [stopPolling]);

    // --- Effect to Manage Polling Intervals (Stable) ---
    useEffect(() => {
        const analysisTypeKeys: (keyof Omit<AppDatasetState, 'dataId' | 'filename' | 'isIntegrated' | 'uploadTime' | 'sourceDataIds' | 'batchLabel' | 'grnInference'>)[] = [
            'basicAnalysis', 'integrationAnalysis', 'trajectoryAnalysis', 'communicationAnalysis', 'velocityAnalysis', 'atacAnalysis'
        ];

        Object.entries(datasets).forEach(([dataId, datasetState]) => {
            analysisTypeKeys.forEach(analysisTypeKey => {
                const analysisState = datasetState[analysisTypeKey];
                // Type guard: ensure analysisState is DatasetAnalysisState (not grnInference)
                if (analysisState && 'taskId' in analysisState && analysisState.taskId && analysisState.status && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(analysisState.status.status)) {
                    const intervalKey = `${dataId}_${analysisTypeKey}_${analysisState.taskId}`;
                    if (!intervalRef.current[intervalKey]) {
                        pollTask(dataId, analysisTypeKey, analysisState.taskId); // Initial poll
                        const intervalId = setInterval(() => {
                             let isStillRelevant = false;
                             setDatasets(prev => { /* Check relevance safely */
                                const currentDs = prev[dataId];
                                const currentAnalysisState = currentDs?.[analysisTypeKey];
                                if (currentAnalysisState && 'taskId' in currentAnalysisState && currentAnalysisState.taskId === analysisState.taskId && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(currentAnalysisState.status?.status ?? '')) { 
                                    isStillRelevant = true; 
                                }
                                return prev;
                             });
                             if (isStillRelevant) { pollTask(dataId, analysisTypeKey, analysisState.taskId); }
                             else { stopPolling(intervalKey); }
                        }, 7000);
                         intervalRef.current = { ...intervalRef.current, [intervalKey]: intervalId };
                    }
                } else if (analysisState && 'taskId' in analysisState && analysisState.taskId) { // Cleanup check
                    const intervalKey = `${dataId}_${analysisTypeKey}_${analysisState.taskId}`;
                    if (intervalRef.current[intervalKey] && analysisState.status && ['SUCCESS', 'FAILURE', 'REVOKED'].includes(analysisState.status.status)) {
                         stopPolling(intervalKey);
                     }
                 }
            });
        });

        return () => { // Cleanup on unmount
            Object.values(intervalRef.current).forEach(clearInterval);
            intervalRef.current = {};
        };
    }, [datasets, pollTask, stopPolling]);


    // --- Selecting Dataset ---
    const handleDatasetSelect = (id: string | null) => setSelectedDataId(id);

    // --- Running Analyses on Selected Dataset ---
    const handleRunAnalysis = async (
        analysisType: AnalysisType, 
        params: any
    ) => {
        if (!selectedDataId) { setGlobalError("No dataset selected."); return; }
        setGlobalError(null);

        // Adjust key based on analysis type (integration handled separately)
        const analysisTypeKey = analysisType === 'integration' ? 'integrationAnalysis' : `${analysisType}Analysis` as keyof AppDatasetState;

        // Initial state update to show PENDING/Submitting
        setDatasets(prev => ({
            ...prev,
            [selectedDataId]: {
                ...prev[selectedDataId],
                [analysisTypeKey]: {
                    taskId: null,
                    status: { task_id: '', status: 'PENDING', result: { status: 'Submitting task...'}},
                    parameters: params,
                    resultsSummary: null,
                    error: null,
                 }
            }
         }));

        try {
            let response: TaskStartResponse;
            let finalParams = { ...params, source_data_id: selectedDataId }; // Add source_data_id for most tasks

            switch (analysisType) {
                case 'basic':
                    response = await startAnalysis(selectedDataId, params as AnalysisParameters);
                    break;
                case 'trajectory':
                    response = await startTrajectory(finalParams as TrajectoryParameters);
                    break;
                case 'communication':
                    response = await startCommunication(finalParams as CellCommunicationParameters);
                    break;
                case 'velocity':
                    response = await startVelocity(finalParams as RnaVelocityParameters);
                    break;
                case 'atac': // <<< ADD THIS CASE
                    response = await startAtacAnalysis(finalParams as AtacAnalysisParameters);
                    break;
                // case 'integration': // Integration is handled by handleStartIntegration
                //     break;
                default:
                    throw new Error(`Invalid analysis type: ${analysisType}`);
            }

            // Update state with actual task ID
            setDatasets(prev => ({
                ...prev,
                [selectedDataId]: {
                    ...prev[selectedDataId],
                    [analysisTypeKey]: {
                        ...(prev[selectedDataId][analysisTypeKey] as any),
                        taskId: response.task_id,
                        status: { task_id: response.task_id, status: 'PENDING', result: null },
                    }
                }
            }));

        } catch (error: any) {
            console.error(`Failed to start ${analysisType} analysis:`, error);
            setGlobalError(`Failed to start ${analysisType} analysis: ${error.message}`);
            // Update state to show start failure
             setDatasets(prev => ({
                ...prev,
                [selectedDataId]: {
                    ...prev[selectedDataId],
                    [analysisTypeKey]: {
                        ...(prev[selectedDataId][analysisTypeKey] as any),
                        taskId: null, status: null,
                        error: `Failed to start task: ${error.message}`
                    }
                }
            }));
        }
    };


    // --- Integration Logic (Unchanged from previous version) ---
    const handleStartIntegration = async (integrationParams: IntegrationParameters) => {
        setGlobalError(null);
        const outputDataId = integrationParams.output_data_id || `integrated_${Date.now()}`;

        setDatasets(prev => ({ /* Add placeholder */
             ...prev,
            [outputDataId]: { dataId: outputDataId, isIntegrated: true, sourceDataIds: integrationParams.files.map(f => f.data_id), uploadTime: new Date().toISOString(), integrationAnalysis: { taskId: null, status: { task_id: '', status: 'PENDING', result: { status: 'Submitting task...'}}, parameters: integrationParams, resultsSummary: null, error: null }}
         }));

        try {
            const response = await startIntegration({ ...integrationParams, output_data_id: outputDataId });
            setDatasets(prev => { /* Update with task ID */
                 const current = prev[outputDataId];
                 if(current?.integrationAnalysis) { return {...prev, [outputDataId]: {...current, integrationAnalysis: {...current.integrationAnalysis, taskId: response.task_id, status: { task_id: response.task_id, status: 'PENDING', result: null }}}}; }
                 return prev;
            });
        } catch (error: any) { /* Handle error */
             console.error('Failed to start integration analysis:', error);
             setGlobalError(`Failed to start integration analysis: ${error.message}`);
             setDatasets(prev => { /* Update placeholder with error */
                const current = prev[outputDataId];
                 if (current?.integrationAnalysis) { return {...prev, [outputDataId]: {...current, integrationAnalysis: {...current.integrationAnalysis, taskId: null, status: null, error: `Failed to start task: ${error.message}`}}}; }
                 return prev;
             });
        }
    };


    const selectedDataset = selectedDataId ? datasets[selectedDataId] : null;
    const selectableDatasets = Object.values(datasets).filter(ds =>
        !(ds.isIntegrated && (!ds.integrationAnalysis || ds.integrationAnalysis.status?.status !== 'SUCCESS'))
    ).reduce((acc, ds) => { acc[ds.dataId] = ds; return acc; }, {} as Record<string, AppDatasetState>);


    // 预处理页面内容
    const renderPreprocessingPage = () => (
        <>
            {globalError && <p className="global-error">Error: {globalError}</p>}
            <section className="app-section">
                <h3>1. Upload & Integrate Data</h3>
                <MultiFileUpload onFilesPrepared={handleFilesPrepared} uploadProgress={uploadProgress} isUploading={isUploading}/>
                <button
                    className="primary-action-btn"
                    onClick={handleConfirmUploads}
                    disabled={filesToUpload.length === 0 || isUploading}
                >
                    <span className="btn-label">{isUploading ? '上传中…' : `上传 ${filesToUpload.length} 个文件`}</span>
                </button>
                <IntegrationConfig availableDatasets={Object.values(datasets).filter(d => !d.isIntegrated)} onStartIntegration={handleStartIntegration} activeIntegrationTask={Object.values(datasets).find(d => d.isIntegrated && d.integrationAnalysis && !['SUCCESS', 'FAILURE'].includes(d.integrationAnalysis.status?.status ?? ''))?.integrationAnalysis}/>
            </section>

            {Object.keys(selectableDatasets).length > 0 && (
                <section className="app-section">
                    <hr /><h3>2. Select Dataset & Analyze</h3>
                    <DatasetSelector datasets={selectableDatasets} onSelect={handleDatasetSelect} selectedId={selectedDataId} />
                    {selectedDataset && ( <AnalysisRunner dataset={selectedDataset} onRunAnalysis={handleRunAnalysis} defaultParams={{ basic: defaultBasicParams, trajectory: defaultTrajectoryParams, communication: defaultCommunicationParams, velocity: defaultVelocityParams,atac:defaultAtacParams}}/> )}
                </section>
            )}

            {selectedDataset && (
                <section className="app-section">
                    <hr /><h3>3. Results for Dataset: {selectedDataset.filename || selectedDataId} {selectedDataset.isIntegrated ? '(Integrated)' : ''}</h3>
                    <ResultsViewer dataset={selectedDataset} />
                </section>
            )}
            
            {Object.keys(datasets).length === 0 && !isUploading && filesToUpload.length === 0 && (
                <p>Upload one or more .h5ad files to begin.</p>
            )}
        </>
    );

    // GRN 推断页面内容
    const renderGRNPage = () => (
        <section className="app-section">
            <h2>基因调控网络推断 (GRN)</h2>
            <p>使用 DeepSEM 算法推断基因调控网络</p>
            <GRNInference onResultsReady={(results) => {
                console.log('GRN 推断完成:', results);
                // 可以在这里保存结果到状态中
            }} />
        </section>
    );

    return (
        <div className="App">
            <header className="App-header"><h1>Single Cell Multi-Analysis App</h1></header>
            <div className="app-body"> 
                <Sidebar activePage={activePage} onPageChange={setActivePage} />
                <main className="main-content">
                    {activePage === 'preprocessing' && renderPreprocessingPage()}
                    {activePage === 'grn' && renderGRNPage()}
                </main>
            </div>
        </div>
    );
}
export default App;