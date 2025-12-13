import React, { useState, useEffect } from 'react';
import { AppDatasetState, AnalysisParameters, TrajectoryParameters, CellCommunicationParameters, RnaVelocityParameters, DatasetAnalysisState, AtacAnalysisParameters } from '../types';
import TaskProgress from './TaskProgress';
import './AnalysisRunner.css';

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
            <div className="analysis-card">
                <div className="analysis-header">
                    <div>
                        <h4>运行分析：{dataset.filename || dataset.dataId}</h4>
                        <p>按需展开参数后再启动，每项任务独立运行。</p>
                    </div>
                </div>

                {/* --- Basic Analysis --- */}
                <div className="analysis-section">
                    <div className="section-head">
                        <div>
                            <h5>基础分析</h5>
                            <p>QC / PCA / UMAP / 聚类 / marker 基因</p>
                        </div>
                        <div className="section-actions">
                            <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => toggleShowParams('basic')}
                                disabled={isTaskRunning(dataset, 'basic')}
                            >
                                {showParams.basic ? '收起参数' : '展开参数'}
                            </button>
                            <button
                                type="button"
                                className="primary-action-btn"
                                onClick={() => onRunAnalysis('basic', basicParams)}
                                disabled={isTaskRunning(dataset, 'basic')}
                            >
                                {isTaskRunning(dataset, 'basic') ? '运行中…' : ((getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.taskId ? '重新运行' : '开始运行')}
                            </button>
                        </div>
                    </div>
                    {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.status && (
                        <TaskProgress status={(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)!.status} />
                    )}
                    {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.error && (
                        <p className="error-message">Error: {(getAnalysisState(dataset, 'basic') as DatasetAnalysisState)?.error}</p>
                    )}
                    {showParams.basic && (
                        <div className="param-panel">
                            <div className="field-row">
                                <label>每细胞最少基因数</label>
                                <input
                                    type="number"
                                    name="min_genes_after_qc"
                                    value={basicParams.min_genes_after_qc ?? ''}
                                    onChange={(e) => handleParamChange(setBasicParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>聚类算法</label>
                                <select
                                    name="clustering_method"
                                    value={basicParams.clustering_method}
                                    onChange={e => handleParamChange(setBasicParams, e)}
                                >
                                    <option value="leiden">Leiden</option>
                                    <option value="louvain">Louvain</option>
                                </select>
                            </div>
                            {/* 可按需补充更多基础参数 */}
                        </div>
                    )}
                </div>

                {/* --- RNA Velocity Analysis --- */}
                <div className="analysis-section">
                    <div className="section-head">
                        <div>
                            <h5>RNA Velocity (scVelo)</h5>
                            <p>需原始数据含 spliced/unspliced 层。</p>
                        </div>
                        <div className="section-actions">
                            <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => toggleShowParams('velocity')}
                                disabled={!canRunVelocity || isTaskRunning(dataset, 'velocity')}
                            >
                                {showParams.velocity ? '收起参数' : '展开参数'}
                            </button>
                            <button
                                type="button"
                                className="primary-action-btn"
                                onClick={() => onRunAnalysis('velocity', velocityParams)}
                                disabled={!canRunVelocity || isTaskRunning(dataset, 'velocity')}
                            >
                                {isTaskRunning(dataset, 'velocity') ? '运行中…' : ((getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.taskId ? '重新运行' : '开始运行')}
                            </button>
                        </div>
                    </div>
                    {!canRunVelocity && <p className="hint-text">通常在未整合的原始数据上运行。</p>}
                    {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.status && (
                        <TaskProgress status={(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)!.status} />
                    )}
                    {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.error && (
                        <p className="error-message">Error: {(getAnalysisState(dataset, 'velocity') as DatasetAnalysisState)?.error}</p>
                    )}
                    {showParams.velocity && canRunVelocity && (
                        <div className="param-panel">
                            <div className="field-row">
                                <label>模式</label>
                                <select name="mode" value={velocityParams.mode} onChange={e => handleParamChange(setVelocityParams, e)}>
                                    <option value="stochastic">stochastic</option>
                                    <option value="deterministic">deterministic</option>
                                    <option value="dynamical">dynamical</option>
                                </select>
                            </div>
                            <div className="field-row">
                                <label>Embedding Basis</label>
                                <input
                                    type="text"
                                    name="embedding_basis"
                                    value={velocityParams.embedding_basis}
                                    onChange={(e) => handleParamChange(setVelocityParams, e)}
                                    placeholder="如：umap"
                                />
                            </div>
                            <div className="field-row">
                                <label>颜色键</label>
                                <input
                                    type="text"
                                    name="color_key"
                                    value={velocityParams.color_key ?? ''}
                                    onChange={(e) => handleParamChange(setVelocityParams, e)}
                                    placeholder="如：clusters"
                                />
                            </div>
                            {/* 可按需补充更多 velocity 参数 */}
                        </div>
                    )}
                </div>

                {/* --- Trajectory Analysis --- */}
                <div className="analysis-section">
                    <div className="section-head">
                        <div>
                            <h5>轨迹分析 (Diffmap / PAGA / DPT)</h5>
                            <p>需基础分析完成且已有聚类结果。</p>
                        </div>
                        <div className="section-actions">
                            <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => toggleShowParams('trajectory')}
                                disabled={!canRunTrajectory || isTaskRunning(dataset, 'trajectory')}
                            >
                                {showParams.trajectory ? '收起参数' : '展开参数'}
                            </button>
                            <button
                                type="button"
                                className="primary-action-btn"
                                onClick={() => onRunAnalysis('trajectory', trajectoryParams)}
                                disabled={!canRunTrajectory || isTaskRunning(dataset, 'trajectory')}
                            >
                                {isTaskRunning(dataset, 'trajectory') ? '运行中…' : ((getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.taskId ? '重新运行' : '开始运行')}
                            </button>
                        </div>
                    </div>
                    {!canRunTrajectory && <p className="hint-text">需要基础分析成功并完成聚类。</p>}
                    {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.status && (
                        <TaskProgress status={(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)!.status} />
                    )}
                    {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.error && (
                        <p className="error-message">Error: {(getAnalysisState(dataset, 'trajectory') as DatasetAnalysisState)?.error}</p>
                    )}
                    {showParams.trajectory && canRunTrajectory && (
                        <div className="param-panel">
                            <div className="field-row">
                                <label>DPT Root Cluster</label>
                                <input
                                    type="text"
                                    name="dpt_root_cluster"
                                    placeholder="必填以计算 DPT"
                                    value={trajectoryParams.dpt_root_cluster ?? ''}
                                    onChange={(e) => handleParamChange(setTrajectoryParams, e)}
                                />
                            </div>
                            {/* 可按需补充更多 trajectory 参数 */}
                        </div>
                    )}
                </div>

                {/* --- Cell Communication Analysis --- */}
                <div className="analysis-section">
                    <div className="section-head">
                        <div>
                            <h5>细胞通信 (CellPhoneDB)</h5>
                            <p>需基础分析完成且已有聚类。</p>
                        </div>
                        <div className="section-actions">
                            <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => toggleShowParams('communication')}
                                disabled={!canRunCommunication || isTaskRunning(dataset, 'communication')}
                            >
                                {showParams.communication ? '收起参数' : '展开参数'}
                            </button>
                            <button
                                type="button"
                                className="primary-action-btn"
                                onClick={() => onRunAnalysis('communication', commParams)}
                                disabled={!canRunCommunication || isTaskRunning(dataset, 'communication')}
                            >
                                {isTaskRunning(dataset, 'communication') ? '运行中…' : ((getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.taskId ? '重新运行' : '开始运行')}
                            </button>
                        </div>
                    </div>
                    {!canRunCommunication && <p className="hint-text">需要基础分析成功并完成聚类。</p>}
                    {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.status && (
                        <TaskProgress status={(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)!.status} />
                    )}
                    {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.error && (
                        <p className="error-message">Error: {(getAnalysisState(dataset, 'communication') as DatasetAnalysisState)?.error}</p>
                    )}
                    {showParams.communication && canRunCommunication && (
                        <div className="param-panel">
                            <div className="field-row">
                                <label>聚类字段</label>
                                <input
                                    type="text"
                                    name="clustering_key"
                                    value={commParams.clustering_key}
                                    onChange={(e) => handleParamChange(setCommParams, e)}
                                />
                            </div>
                            <p className="hint-text">提示：服务器需配置 CellPhoneDB 数据库路径。</p>
                            {/* 可按需补充更多通信参数 */}
                        </div>
                    )}
                </div>

                {/* --- ATAC Analysis Section --- */}
                <div className="analysis-section">
                    <div className="section-head">
                        <div>
                            <h5>ATAC 分析 (Muon)</h5>
                            <p>支持独立运行，适用于上传的 ATAC 数据。</p>
                        </div>
                        <div className="section-actions">
                            <button
                                type="button"
                                className="ghost-btn"
                                onClick={() => toggleShowParams('atac')}
                                disabled={!canRunAtac || isTaskRunning(dataset, 'atac')}
                            >
                                {showParams.atac ? '收起参数' : '展开参数'}
                            </button>
                            <button
                                type="button"
                                className="primary-action-btn"
                                onClick={() => onRunAnalysis('atac', atacParams)}
                                disabled={!canRunAtac || isTaskRunning(dataset, 'atac')}
                            >
                                {isTaskRunning(dataset, 'atac') ? '运行中…' : ((getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.taskId ? '重新运行' : '开始运行')}
                            </button>
                        </div>
                    </div>
                    {!canRunAtac && <p className="hint-text">需先上传 ATAC 数据集。</p>}
                    {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.status && (
                        <TaskProgress status={(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)!.status} />
                    )}
                    {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.error && (
                        <p className="error-message">Error: {(getAnalysisState(dataset, 'atac') as DatasetAnalysisState)?.error}</p>
                    )}
                    {showParams.atac && canRunAtac && (
                        <div className="param-panel">
                            <div className="field-row">
                                <label>最少计数/细胞</label>
                                <input
                                    type="number"
                                    name="qc_min_counts"
                                    value={atacParams.qc_min_counts}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>最大计数分位</label>
                                <input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    max="1"
                                    name="qc_max_counts_quantile"
                                    value={atacParams.qc_max_counts_quantile}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>TF-IDF</label>
                                <input
                                    type="checkbox"
                                    name="tfidf_transform"
                                    checked={atacParams.tfidf_transform}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>LSI 维度数</label>
                                <input
                                    type="number"
                                    name="lsi_n_components"
                                    value={atacParams.lsi_n_components}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>邻居 (LSI)</label>
                                <input
                                    type="number"
                                    name="neighbors_n_pcs"
                                    value={atacParams.neighbors_n_pcs}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            <div className="field-row">
                                <label>聚类分辨率</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    name="clustering_resolution"
                                    value={atacParams.clustering_resolution}
                                    onChange={(e) => handleParamChange(setAtacParams, e)}
                                />
                            </div>
                            {/* 可按需补充更多 ATAC 参数 */}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AnalysisRunner;