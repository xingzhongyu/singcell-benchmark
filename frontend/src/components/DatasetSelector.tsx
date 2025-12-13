import React from 'react';
import { AppDatasetState } from '../types';
import './DatasetSelector.css';

interface DatasetSelectorProps {
    datasets: Record<string, AppDatasetState>;
    onSelect: (id: string | null) => void;
    selectedId: string | null;
}

const DatasetSelector: React.FC<DatasetSelectorProps> = ({ datasets, onSelect, selectedId }) => {
    const datasetList = Object.values(datasets);

    if (datasetList.length === 0) {
        return <p className="dataset-selector-empty">暂无可用数据集，请先上传数据。</p>;
    }

    return (
        <div className="dataset-selector">
            <div className="selector-row">
                <label htmlFor="dataset-select">选择数据集</label>
                <select
                    id="dataset-select"
                    value={selectedId ?? ""}
                    onChange={(e) => onSelect(e.target.value || null)}
                >
                    <option value="">-- 请选择 --</option>
                    {datasetList.map(ds => (
                        <option key={ds.dataId} value={ds.dataId}>
                            {ds.filename || ds.dataId} {ds.isIntegrated ? '(Integrated)' : ''}
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
};

export default DatasetSelector;