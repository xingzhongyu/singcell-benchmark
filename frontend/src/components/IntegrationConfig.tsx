import React, { useState, useEffect } from 'react';
import { IntegrationParameters, AppDatasetState, TaskStatus } from '../types'; // Assuming DatasetAnalysisState is part of AppDatasetState
import TaskProgress from './TaskProgress';
// import './styles.css';

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
            <h4>Integrate Datasets</h4>
            {availableDatasets.length < 2 && <p>Upload at least two datasets to enable integration.</p>}
            {availableDatasets.length >= 2 && (
                <form onSubmit={handleSubmit}>
                    <p>Select datasets to integrate:</p>
                    {availableDatasets.map(ds => (
                        <div key={ds.dataId}>
                            <input
                                type="checkbox"
                                id={`integrate-${ds.dataId}`}
                                checked={selectedDataIds.includes(ds.dataId)}
                                onChange={() => handleCheckboxChange(ds.dataId)}
                                disabled={isBusy}
                            />
                            <label htmlFor={`integrate-${ds.dataId}`}>{ds.filename || ds.dataId}</label>
                        </div>
                    ))}

                    <div>
                        <label htmlFor="integration-method">Method: </label>
                        <select id="integration-method" value={method} onChange={e => setMethod(e.target.value as 'bbknn' | 'harmony')} disabled={isBusy}>
                            <option value="bbknn">BBKNN</option>
                            <option value="harmony">Harmony</option>
                        </select>
                    </div>
                    <div>
                        <label htmlFor="batch-key">Batch Key (adata.obs): </label>
                        <input type="text" id="batch-key" value={batchKey} onChange={e => setBatchKey(e.target.value)} required disabled={isBusy}/>
                    </div>
                     {/* Add more parameter inputs for BBKNN/Harmony/Post-steps here */}

                    <button type="submit" disabled={selectedDataIds.length < 2 || isBusy}>
                        {isBusy ? 'Integration Running...' : 'Start Integration'}
                    </button>
                     {activeIntegrationTask && activeIntegrationTask.status && (
                         <div style={{marginTop: '10px'}}>
                             <TaskProgress status={activeIntegrationTask.status} />
                         </div>
                     )}
                </form>
            )}
        </div>
    );
};

export default IntegrationConfig;