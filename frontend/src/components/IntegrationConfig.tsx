import React, { useState, useEffect } from 'react';
import { IntegrationParameters, AppDatasetState, TaskStatus } from '../types'; // Assuming DatasetAnalysisState is part of AppDatasetState
import TaskProgress from './TaskProgress';
import './IntegrationConfig.css';

interface IntegrationConfigProps {
    availableDatasets: AppDatasetState[]; // Pass original uploaded datasets
    onStartIntegration: (params: IntegrationParameters) => void;
    activeIntegrationTask?: AppDatasetState['integrationAnalysis']; // Pass status of running integration task
}

const IntegrationConfig: React.FC<IntegrationConfigProps> = ({
    availableDatasets,
    onStartIntegration,
    activeIntegrationTask
}) => {
    const [selectedDataIds, setSelectedDataIds] = useState<string[]>([]);
    const [method, setMethod] = useState<'bbknn' | 'harmony'>('bbknn');
    // Add state for other integration parameters if needed (e.g., neighbors, theta)
    const [batchKey, setBatchKey] = useState<string>('batch'); // Default key


    const handleCheckboxChange = (dataId: string) => {
        setSelectedDataIds(prev =>
            prev.includes(dataId)
                ? prev.filter(id => id !== dataId)
                : [...prev, dataId]
        );
    };

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault();
        if (selectedDataIds.length < 2) {
            alert("Please select at least two datasets to integrate.");
            return;
        }

        // Find corresponding batch labels from availableDatasets
        const filesToIntegrate = selectedDataIds.map(id => {
             const ds = availableDatasets.find(d => d.dataId === id);
             // Find the batch label assigned during upload - HOW?
             // We need to store the original batch label with the AppDatasetState
             // For now, derive it from filename or assume it's stored
             const filename = ds?.filename || `${id}_data`;
             return { data_id: id, batch_label: ds?.batchLabel || `Batch_${filename.split('.')[0]}` }; // *** Needs improvement *** Store batch label in AppDatasetState
        });


        const params: IntegrationParameters = {
            integration_method: method,
            files: filesToIntegrate,
            // output_data_id: `integrated_${Date.now()}`, // App.tsx can generate this
            bbknn_batch_key: batchKey, // Use state
            bbknn_neighbors_within_batch: 3, // Example default
            harmony_batch_key: batchKey, // Use state
            harmony_theta: 2.0, // Example default
            harmony_max_iter_harmony: 10, // Example default
            // Include other params based on UI controls
            run_pca: true,
            pca_n_comps: 50,
            run_neighbors: true,
            neighbors_n_pcs: 30,
            neighbors_n_neighbors: 15,
            run_umap: true,
            umap_min_dist: 0.5,
            umap_spread: 1.0,
        };
        onStartIntegration(params);
    };

    const isBusy = !!activeIntegrationTask && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(activeIntegrationTask.status?.status ?? '');

    return (
        <div className="integration-config">
            <div className="integration-card">
                <div className="integration-header">
                    <div>
                        <h4>整合数据集</h4>
                        <p>选择至少 2 个数据集并指定批次字段，支持 BBKNN / Harmony。</p>
                    </div>
                    <span className={`tag ${isBusy ? 'tag-busy' : 'tag-idle'}`}>
                        {isBusy ? '运行中' : '待启动'}
                    </span>
                </div>

                {availableDatasets.length < 2 && (
                    <div className="integration-empty">请先上传至少两个数据集以启用整合。</div>
                )}

            {availableDatasets.length >= 2 && (
                    <form onSubmit={handleSubmit} className="integration-form">
                        <div className="section-title">选择待整合的数据集：</div>
                        <div className="dataset-list">
                    {availableDatasets.map(ds => (
                                <label key={ds.dataId} className="dataset-item">
                            <input
                                type="checkbox"
                                checked={selectedDataIds.includes(ds.dataId)}
                                onChange={() => handleCheckboxChange(ds.dataId)}
                                disabled={isBusy}
                            />
                                    <span className="dataset-name">{ds.filename || ds.dataId}</span>
                                </label>
                            ))}
                        </div>

                        <div className="field-row">
                            <label htmlFor="integration-method">整合方法</label>
                            <select
                                id="integration-method"
                                value={method}
                                onChange={e => setMethod(e.target.value as 'bbknn' | 'harmony')}
                                disabled={isBusy}
                            >
                            <option value="bbknn">BBKNN</option>
                            <option value="harmony">Harmony</option>
                        </select>
                    </div>

                        <div className="field-row">
                            <label htmlFor="batch-key">批次字段 (adata.obs)</label>
                            <input
                                type="text"
                                id="batch-key"
                                value={batchKey}
                                onChange={e => setBatchKey(e.target.value)}
                                required
                                disabled={isBusy}
                                placeholder="例如：batch"
                            />
                    </div>

                        <div className="action-row">
                            <button
                                type="submit"
                                className="primary-action-btn"
                                disabled={selectedDataIds.length < 2 || isBusy}
                            >
                                {isBusy ? '整合进行中…' : '开始整合'}
                    </button>
                        </div>

                     {activeIntegrationTask && activeIntegrationTask.status && (
                            <div className="progress-wrapper">
                             <TaskProgress status={activeIntegrationTask.status} />
                         </div>
                     )}
                </form>
            )}
            </div>
        </div>
    );
};

export default IntegrationConfig;