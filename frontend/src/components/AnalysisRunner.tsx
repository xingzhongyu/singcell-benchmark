import React, { useState, useEffect } from 'react';
import { AppDatasetState, AnalysisParameters, TrajectoryParameters, CellCommunicationParameters, RnaVelocityParameters, DatasetAnalysisState, AtacAnalysisParameters } from '../types';
import TaskProgress from './TaskProgress';

// Define the AnalysisType locally or import if defined globally
type AnalysisType = 'basic' | 'trajectory' | 'communication' | 'velocity'| 'atac';

interface AnalysisRunnerProps {
    dataset: AppDatasetState;
    onRunAnalysis: (analysisType: AnalysisType, params: any) => void;
    // Pass default parameters for initialization
    defaultParams: {
        basic: AnalysisParameters;
        trajectory: Omit<TrajectoryParameters, 'source_data_id'>;
        communication: Omit<CellCommunicationParameters, 'source_data_id'>;
        velocity: Omit<RnaVelocityParameters, 'source_data_id'>;
        atac:Omit<AtacAnalysisParameters,'source_data_id'>
    };
}

// Helper function to get analysis state safely
const getAnalysisState = (dataset: AppDatasetState, type: AnalysisType) => {
    const key = `${type}Analysis` as keyof AppDatasetState;
    return dataset[key];
}

// Helper function to check if a task is running
const isTaskRunning = (dataset: AppDatasetState, type: AnalysisType) => {
    const state = getAnalysisState(dataset, type);
    return !!(state as DatasetAnalysisState)?.taskId && !['SUCCESS', 'FAILURE', 'REVOKED'].includes((state as DatasetAnalysisState).status?.status ?? '');
}

const AnalysisRunner: React.FC<AnalysisRunnerProps> = ({ dataset, onRunAnalysis, defaultParams }) => {
    // State for showing parameter sections
    const [showParams, setShowParams] = useState<Record<AnalysisType, boolean>>({
        basic: false, trajectory: false, communication: false, velocity: false,atac:false
    });

    // State for parameters of each analysis type, initialized correctly
    const [basicParams, setBasicParams] = useState<AnalysisParameters>(
        () => (getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.parameters || defaultParams.basic
    );
    const [trajectoryParams, setTrajectoryParams] = useState<Omit<TrajectoryParameters, 'source_data_id'>>(
        () => (getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.parameters || defaultParams.trajectory
    );
    const [commParams, setCommParams] = useState<Omit<CellCommunicationParameters, 'source_data_id'>>(
        () => (getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.parameters || defaultParams.communication
    );
    const [velocityParams, setVelocityParams] = useState<Omit<RnaVelocityParameters, 'source_data_id'>>(
        () => (getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.parameters || defaultParams.velocity
    );
    const [atacParams, setAtacParams] = useState<Omit<AtacAnalysisParameters, 'source_data_id'>>(
        () => (getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.parameters || defaultParams.atac
   );

    // Reset parameters if the selected dataset changes
    useEffect(() => {
        setBasicParams((getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.parameters || defaultParams.basic);
        setTrajectoryParams((getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.parameters || defaultParams.trajectory);
        setCommParams((getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.parameters || defaultParams.communication);
        setVelocityParams((getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.parameters || defaultParams.velocity);
        setAtacParams((getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.parameters || defaultParams.atac);
        // Reset visibility state too if desired
        // setShowParams({ basic: false, trajectory: false, communication: false, velocity: false });
    }, [dataset.dataId, defaultParams]); // Rerun when dataset ID changes

    const toggleShowParams = (type: AnalysisType) => {
        setShowParams(prev => ({ ...prev, [type]: !prev[type] }));
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

    // Determine if prerequisites are met
    const basicAnalysisDone = (getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.status?.status === 'SUCCESS';
    const clusteringDone = basicAnalysisDone && (getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.resultsSummary?.clustering_done;
    // Velocity doesn't have strict prerequisites other than potentially needing the original file (checked by API)
    const canRunVelocity = !dataset.isIntegrated; // Typically run on original data, adjust if needed
    const canRunTrajectory = clusteringDone;
    const canRunCommunication = clusteringDone;
    // Prerequisites (ATAC can run independently on uploaded data)
    const canRunAtac = !!dataset.dataId; // Simple check, assumes suitable upload
    return (
        <div className="analysis-runner">
            <h4>Run Analyses on: {dataset.filename || dataset.dataId}</h4>

            {/* --- Basic Analysis --- */}
            <div className="analysis-section">
                <h5>Basic Analysis (QC, PCA, UMAP, Clustering, Markers)</h5>
                <button onClick={() => toggleShowParams('basic')} disabled={isTaskRunning(dataset, 'basic')}> {showParams.basic ? 'Hide' : 'Show'} Params </button>
                <button onClick={() => onRunAnalysis('basic', basicParams)} disabled={isTaskRunning(dataset, 'basic')}>
                    {isTaskRunning(dataset, 'basic') ? 'Running...' : ((getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.taskId ? 'Re-run' : 'Run')} Basic Analysis
                </button>
                {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.status && <TaskProgress status={(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)!.status} />}
                {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.error && <p className='error-message'>Error: {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.error}</p>}
                {showParams.basic && (<div className="param-details"> {/* Add Basic Param Inputs Here */}
                    <label>Min Genes/Cell:</label> <input type="number" name="min_genes_after_qc" value={basicParams.min_genes_after_qc ?? ''} onChange={(e) => handleParamChange(setBasicParams, e)} /> <br/>
                    <label>Clustering:</label> <select name="clustering_method" value={basicParams.clustering_method} onChange={e => handleParamChange(setBasicParams, e)}><option value="leiden">Leiden</option><option value="louvain">Louvain</option></select>
                    {/* ... more basic params ... */}
                </div>)}
            </div>

             {/* --- RNA Velocity Analysis --- */}
             <div className="analysis-section">
                 <h5>RNA Velocity Analysis (scVelo)</h5>
                 {!canRunVelocity && <p><i>(Typically run on original, non-integrated data containing spliced/unspliced layers)</i></p>}
                 <button onClick={() => toggleShowParams('velocity')} disabled={!canRunVelocity || isTaskRunning(dataset, 'velocity')}> {showParams.velocity ? 'Hide' : 'Show'} Params </button>
                 <button onClick={() => onRunAnalysis('velocity', velocityParams)} disabled={!canRunVelocity || isTaskRunning(dataset, 'velocity')}>
                      {isTaskRunning(dataset, 'velocity') ? 'Running...' : ((getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.taskId ? 'Re-run' : 'Run')} RNA Velocity
                 </button>
                 {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.status && <TaskProgress status={(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)!.status} />}
                 {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.error && <p className='error-message'>Error: {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.error}</p>}
                 {showParams.velocity && canRunVelocity && (<div className="param-details"> {/* Add Velocity Param Inputs Here */}
                    <label>Mode:</label> <select name="mode" value={velocityParams.mode} onChange={e => handleParamChange(setVelocityParams, e)}><option value="stochastic">stochastic</option><option value="deterministic">deterministic</option><option value="dynamical">dynamical</option></select> <br/>
                    <label>Embedding Basis:</label> <input type="text" name="embedding_basis" value={velocityParams.embedding_basis} onChange={(e) => handleParamChange(setVelocityParams, e)} placeholder="e.g., umap" /> <br/>
                    <label>Color Key:</label> <input type="text" name="color_key" value={velocityParams.color_key ?? ''} onChange={(e) => handleParamChange(setVelocityParams, e)} placeholder="e.g., clusters" /> <br/>
                    {/* ... more velocity params ... */}
                </div>)}
             </div>

            {/* --- Trajectory Analysis --- */}
            <div className="analysis-section">
                <h5>Trajectory Analysis (Diffmap, PAGA, DPT)</h5>
                {!canRunTrajectory && <p><i>Requires successful Basic Analysis with clustering.</i></p>}
                <button onClick={() => toggleShowParams('trajectory')} disabled={!canRunTrajectory || isTaskRunning(dataset, 'trajectory')}>{showParams.trajectory ? 'Hide' : 'Show'} Params</button>
                <button onClick={() => onRunAnalysis('trajectory', trajectoryParams)} disabled={!canRunTrajectory || isTaskRunning(dataset, 'trajectory')}>
                    {isTaskRunning(dataset, 'trajectory') ? 'Running...' : ((getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.taskId ? 'Re-run' : 'Run')} Trajectory
                </button>
                {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.status && <TaskProgress status={(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)!.status} />}
                {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.error && <p className='error-message'>Error: {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.error}</p>}
                {showParams.trajectory && canRunTrajectory && (<div className="param-details"> {/* Add Trajectory Param Inputs Here */}
                    <label>DPT Root Cluster:</label><input type="text" name="dpt_root_cluster" placeholder="Required for DPT" value={trajectoryParams.dpt_root_cluster ?? ''} onChange={(e) => handleParamChange(setTrajectoryParams, e)} />
                     {/* ... more trajectory params ... */}
                </div>)}
            </div>

            {/* --- Cell Communication Analysis --- */}
            <div className="analysis-section">
                 <h5>Cell Communication (CellPhoneDB)</h5>
                 {!canRunCommunication && <p><i>Requires successful Basic Analysis with clustering.</i></p>}
                 <button onClick={() => toggleShowParams('communication')} disabled={!canRunCommunication || isTaskRunning(dataset, 'communication')}>{showParams.communication ? 'Hide' : 'Show'} Params</button>
                 <button onClick={() => onRunAnalysis('communication', commParams)} disabled={!canRunCommunication || isTaskRunning(dataset, 'communication')}>
                    {isTaskRunning(dataset, 'communication') ? 'Running...' : ((getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.taskId ? 'Re-run' : 'Run')} Communication
                 </button>
                 {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.status && <TaskProgress status={(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)!.status} />}
                 {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.error && <p className='error-message'>Error: {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.error}</p>}
                 {showParams.communication && canRunCommunication && (<div className="param-details"> {/* Add Communication Param Inputs Here */}
                     <label>Clustering Key:</label><input type="text" name="clustering_key" value={commParams.clustering_key} onChange={(e) => handleParamChange(setCommParams, e)} />
                     {/* ... more comm params ... */}
                      <p><i>Note: CellPhoneDB database path must be configured on the server.</i></p>
                 </div>)}
             </div>
             {/* --- ATAC Analysis Section --- */}
        <div className="analysis-section">
             <h5>ATAC Analysis (Muon)</h5>
             {!canRunAtac && <p><i>Requires an uploaded ATAC dataset.</i></p>}
             <button onClick={() => toggleShowParams('atac')} disabled={!canRunAtac || isTaskRunning(dataset, 'atac')}>{showParams.atac ? 'Hide' : 'Show'} Params</button>
             <button onClick={() => onRunAnalysis('atac', atacParams)} disabled={!canRunAtac || isTaskRunning(dataset, 'atac')}>
                 {isTaskRunning(dataset, 'atac') ? 'Running...' : ((getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.taskId ? 'Re-run' : 'Run')} ATAC Analysis
             </button>
             {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.status && <TaskProgress status={(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)!.status} />}
             {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.error && <p className='error-message'>Error: {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.error}</p>}
             {showParams.atac && canRunAtac && (<div className="param-details"> {/* Add ATAC Param Inputs Here */}
                <label>Min Counts/Cell:</label> <input type="number" name="qc_min_counts" value={atacParams.qc_min_counts} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                <label>Max Counts Quantile:</label> <input type="number" step="0.01" min="0" max="1" name="qc_max_counts_quantile" value={atacParams.qc_max_counts_quantile} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                <label>TF-IDF:</label> <input type="checkbox" name="tfidf_transform" checked={atacParams.tfidf_transform} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                <label>LSI Components:</label> <input type="number" name="lsi_n_components" value={atacParams.lsi_n_components} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                <label>Neighbors (LSI):</label> <input type="number" name="neighbors_n_pcs" value={atacParams.neighbors_n_pcs} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                <label>Clustering Resolution:</label> <input type="number" step="0.1" name="clustering_resolution" value={atacParams.clustering_resolution} onChange={(e) => handleParamChange(setAtacParams, e)} /> <br/>
                {/* ... more atac params ... */}
            </div>)}
        </div>
        </div>
    );
};

export default AnalysisRunner;