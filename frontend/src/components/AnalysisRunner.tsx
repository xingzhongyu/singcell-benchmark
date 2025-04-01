import React, { useState } from 'react';
import { AppDatasetState, AnalysisParameters, TrajectoryParameters, CellCommunicationParameters, DatasetAnalysisState } from '../types';
import TaskProgress from './TaskProgress';
// import './styles.css';

interface AnalysisRunnerProps {
    dataset: AppDatasetState;
    onRunAnalysis: (
        analysisType: 'basic' | 'trajectory' | 'communication',
        params: any
    ) => void;
}

// Define default parameters here or import them
const defaultBasicParams: AnalysisParameters = { mito_prefix: 'MT-', min_genes_after_qc: 200, min_cells_after_qc: 3, select_hvgs: true, hvg_min_mean: 0.0125, hvg_max_mean: 3, hvg_min_disp: 0.5, hvg_n_top_genes: null, normalize_target_sum: 10000, pca_n_comps: 50, neighbors_n_pcs: 30, neighbors_n_neighbors: 15, umap_min_dist: 0.5, umap_spread: 1.0, clustering_method: 'leiden', leiden_resolution: 0.5, louvain_resolution: 0.5, marker_gene_method: 'wilcoxon', marker_gene_n_genes: 25 };
const defaultTrajectoryParams: Omit<TrajectoryParameters, 'source_data_id'> = { run_diffmap: true, diffmap_n_comps: 15, run_paga: true, paga_clustering_key: "clusters", paga_threshold_connectivities: 0.05, paga_threshold_confidence: 0.01, calculate_dpt: true, dpt_root_cluster: null }; // Root cluster needs UI input
const defaultCommunicationParams: Omit<CellCommunicationParameters, 'source_data_id'> = { clustering_key: "clusters", counts_layer: null, gene_id_column: null, output_path_suffix: "cellphonedb_out", threads: 4, subsampling: false, subsampling_num_pc: 100, subsampling_log: false };


const AnalysisRunner: React.FC<AnalysisRunnerProps> = ({ dataset, onRunAnalysis }) => {
    const [showBasicParams, setShowBasicParams] = useState(false);
    const [basicParams, setBasicParams] = useState<AnalysisParameters>(dataset.basicAnalysis?.parameters || defaultBasicParams);

    const [showTrajectoryParams, setShowTrajectoryParams] = useState(false);
    const [trajectoryParams, setTrajectoryParams] = useState<Omit<TrajectoryParameters, 'source_data_id'>>(dataset.trajectoryAnalysis?.parameters || defaultTrajectoryParams);

    const [showCommParams, setShowCommParams] = useState(false);
    const [commParams, setCommParams] = useState<Omit<CellCommunicationParameters, 'source_data_id'>>(dataset.communicationAnalysis?.parameters || defaultCommunicationParams);

    // Determine if prerequisites are met
    const basicAnalysisDone = dataset.basicAnalysis?.status?.status === 'SUCCESS';
    // Trajectory requires clustering from basic analysis
    const canRunTrajectory = basicAnalysisDone && dataset.basicAnalysis?.resultsSummary?.clustering_done;
    // Communication requires clustering
    const canRunCommunication = basicAnalysisDone && dataset.basicAnalysis?.resultsSummary?.clustering_done;

     const getTaskState = (analysisType: 'basic' | 'trajectory' | 'communication') => {
         const key = `${analysisType}Analysis` as keyof AppDatasetState;
         return dataset[key] as DatasetAnalysisState
     }

    const isTaskRunning = (analysisType: 'basic' | 'trajectory' | 'communication') => {
         const state = getTaskState(analysisType);
         return !!state?.taskId && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(state.status?.status ?? '');
     };

     const handleParamChange = (
        setter: React.Dispatch<React.SetStateAction<any>>,
        event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
     ) => {
        const { name, value, type } = event.target;
        let parsedValue: any = value;
        if (type === 'number') parsedValue = value === '' ? null : parseFloat(value);
         else if (type === 'checkbox') parsedValue = (event.target as HTMLInputElement).checked;
        setter((prev: any) => ({ ...prev, [name]: parsedValue }));
    };

    return (
        <div className="analysis-runner">
            <h4>Run Analyses on: {dataset.filename || dataset.dataId}</h4>

            {/* --- Basic Analysis --- */}
            <div className="analysis-section">
                <h5>Basic Analysis (QC, PCA, UMAP, Clustering, Markers)</h5>
                <button onClick={() => setShowBasicParams(!showBasicParams)} disabled={isTaskRunning('basic')}>
                    {showBasicParams ? 'Hide Parameters' : 'Show Parameters'}
                </button>
                <button onClick={() => onRunAnalysis('basic', basicParams)} disabled={isTaskRunning('basic')}>
                    {isTaskRunning('basic') ? 'Running...' : (dataset.basicAnalysis?.taskId ? 'Re-run Basic Analysis' : 'Run Basic Analysis')}
                </button>
                {getTaskState('basic')?.status && <TaskProgress status={getTaskState('basic')!.status} />}
                 {getTaskState('basic')?.error && <p className='error-message'>Error: {getTaskState('basic')?.error}</p>}

                {showBasicParams && (
                    <div className="param-details">
                        {/* Add input fields for basicParams, e.g.: */}
                        <label>Min Genes/Cell:</label>
                        <input type="number" name="min_genes_after_qc" value={basicParams.min_genes_after_qc ?? ''} onChange={(e) => handleParamChange(setBasicParams, e)} />
                        {/* ... many more parameters ... */}
                    </div>
                )}
            </div>

            {/* --- Trajectory Analysis --- */}
            <div className="analysis-section">
                 <h5>Trajectory Analysis (Diffmap, PAGA, DPT)</h5>
                 {!canRunTrajectory && <p><i>Requires successful Basic Analysis with clustering.</i></p>}
                 <button onClick={() => setShowTrajectoryParams(!showTrajectoryParams)} disabled={!canRunTrajectory || isTaskRunning('trajectory')}>
                     {showTrajectoryParams ? 'Hide Parameters' : 'Show Parameters'}
                 </button>
                 <button onClick={() => onRunAnalysis('trajectory', trajectoryParams)} disabled={!canRunTrajectory || isTaskRunning('trajectory')}>
                     {isTaskRunning('trajectory') ? 'Running...' : (dataset.trajectoryAnalysis?.taskId ? 'Re-run Trajectory' : 'Run Trajectory')}
                 </button>
                {getTaskState('trajectory')?.status && <TaskProgress status={getTaskState('trajectory')!.status} />}
                 {getTaskState('trajectory')?.error && <p className='error-message'>Error: {getTaskState('trajectory')?.error}</p>}

                {showTrajectoryParams && canRunTrajectory && (
                    <div className="param-details">
                         {/* Add inputs for trajectoryParams */}
                         <label>Clustering Key:</label>
                        <input type="text" name="paga_clustering_key" value={trajectoryParams.paga_clustering_key} onChange={(e) => handleParamChange(setTrajectoryParams, e)} />
                         <label>DPT Root Cluster:</label>
                         <input type="text" name="dpt_root_cluster" placeholder="Required for DPT" value={trajectoryParams.dpt_root_cluster ?? ''} onChange={(e) => handleParamChange(setTrajectoryParams, e)} />
                        {/* ... other parameters ... */}
                    </div>
                )}
             </div>


            {/* --- Cell Communication Analysis --- */}
             <div className="analysis-section">
                 <h5>Cell Communication (CellPhoneDB)</h5>
                 {!canRunCommunication && <p><i>Requires successful Basic Analysis with clustering.</i></p>}
                 <button onClick={() => setShowCommParams(!showCommParams)} disabled={!canRunCommunication || isTaskRunning('communication')}>
                     {showCommParams ? 'Hide Parameters' : 'Show Parameters'}
                 </button>
                 <button onClick={() => onRunAnalysis('communication', commParams)} disabled={!canRunCommunication || isTaskRunning('communication')}>
                      {isTaskRunning('communication') ? 'Running...' : (dataset.communicationAnalysis?.taskId ? 'Re-run Communication' : 'Run Communication')}
                 </button>
                 {getTaskState('communication')?.status && <TaskProgress status={getTaskState('communication')!.status} />}
                 {getTaskState('communication')?.error && <p className='error-message'>Error: {getTaskState('communication')?.error}</p>}

                 {showCommParams && canRunCommunication && (
                    <div className="param-details">
                         {/* Add inputs for commParams */}
                         <label>Clustering Key:</label>
                        <input type="text" name="clustering_key" value={commParams.clustering_key} onChange={(e) => handleParamChange(setCommParams, e)} />
                        {/* ... other parameters ... */}
                         <p><i>Note: CellPhoneDB database path must be configured on the server.</i></p>
                    </div>
                )}
             </div>

        </div>
    );
};

export default AnalysisRunner;