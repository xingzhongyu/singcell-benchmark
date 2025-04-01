import React from 'react';
import { AppDatasetState } from '../types';
// import './styles.css';

interface DatasetSelectorProps {
    datasets: Record<string, AppDatasetState>;
    onSelect: (id: string | null) => void;
    selectedId: string | null;
}

const DatasetSelector: React.FC<DatasetSelectorProps> = ({ datasets, onSelect, selectedId }) => {
    const datasetList = Object.values(datasets);

    if (datasetList.length === 0) {
        return <p>No datasets available yet. Upload data to begin.</p>;
    }

    return (
        <div className="dataset-selector">
            <label htmlFor="dataset-select">Select Dataset: </label>
            <select
                id="dataset-select"
                value={selectedId ?? ""}
                onChange={(e) => onSelect(e.target.value || null)}
            >
                <option value="">-- Select a Dataset --</option>
                {datasetList.map(ds => (
                    <option key={ds.dataId} value={ds.dataId}>
                        {ds.filename || ds.dataId} {ds.isIntegrated ? '(Integrated)' : ''}
                    </option>
                ))}
            </select>
        </div>
    );
};

export default DatasetSelector;