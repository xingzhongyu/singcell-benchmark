import React, { useState, ChangeEvent } from 'react';
import './MultiFileUpload.css';

interface PreparedFile {
    file: File;
    batchLabel: string;
    id: string; // Unique ID for tracking progress
}

interface MultiFileUploadProps {
    onFilesPrepared: (files: PreparedFile[]) => void;
    uploadProgress: Record<string, { status: string; message?: string }>;
    isUploading: boolean;
}

const MultiFileUpload: React.FC<MultiFileUploadProps> = ({ onFilesPrepared, uploadProgress, isUploading }) => {
    const [preparedFiles, setPreparedFiles] = useState<PreparedFile[]>([]);

    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files) {
            const newPreparedFiles: PreparedFile[] = Array.from(files).map((file, index) => ({
                file,
                // Default batch label, user should edit this
                batchLabel: `Batch_${file.name.split('.')[0] || index + 1}`,
                id: `${file.name}_${file.lastModified}` // Simple unique ID
            }));
            setPreparedFiles(prev => [...prev, ...newPreparedFiles]);
            onFilesPrepared([...preparedFiles, ...newPreparedFiles]); // Update parent immediately
        }
        // Clear the input value so the same file can be selected again
        event.target.value = '';
    };

    const handleLabelChange = (id: string, newLabel: string) => {
        const updatedFiles = preparedFiles.map(pf =>
            pf.id === id ? { ...pf, batchLabel: newLabel } : pf
        );
        setPreparedFiles(updatedFiles);
        onFilesPrepared(updatedFiles); // Update parent state
    };

    const removeFile = (id: string) => {
         const updatedFiles = preparedFiles.filter(pf => pf.id !== id);
         setPreparedFiles(updatedFiles);
         onFilesPrepared(updatedFiles); // Update parent state
    };


    return (
        <div className="multi-file-upload">
            <div className="upload-card">
                <div className="upload-header">
                    <div>
                        <h3>批量上传 .h5ad</h3>
                        <p>为每个文件设定批次标签，支持多选添加。</p>
                    </div>
                    <span className={`upload-state ${isUploading ? 'state-uploading' : 'state-idle'}`}>
                        {isUploading ? '上传中…' : '待上传'}
                    </span>
                </div>

                <label htmlFor="file-input" className="file-dropzone" aria-label="选择 .h5ad 文件">
                    <div className="drop-main">选择或拖拽文件</div>
                    <div className="drop-sub">仅支持 .h5ad，点击即可打开文件选择器</div>
            </label>
            <input
                id="file-input"
                type="file"
                accept=".h5ad"
                multiple
                onChange={handleFileChange}
                disabled={isUploading}
                    style={{ display: 'none' }}
            />

                <p className="helper-text">已选文件可在下方修改批次名，上传完成的记录会锁定编辑。</p>

                {preparedFiles.length === 0 && (
                    <div className="empty-state">
                        <span>暂无文件，请先选择或拖拽 .h5ad 文件。</span>
                    </div>
                )}

                <ul className="file-list">
                {preparedFiles.map((pf) => (
                        <li key={pf.id} className="file-item">
                            <div className="file-info">
                                <div className="file-name">{pf.file.name}</div>
                        <input
                                    className="batch-input"
                            type="text"
                            value={pf.batchLabel}
                            onChange={(e) => handleLabelChange(pf.id, e.target.value)}
                                    placeholder="批次标签"
                            disabled={isUploading || uploadProgress[pf.id]?.status === 'success'}
                        />
                            </div>
                            <div className="file-actions">
                        {uploadProgress[pf.id] && (
                                    <span className={`upload-status status-${uploadProgress[pf.id].status}`}>
                                        {uploadProgress[pf.id].status}{uploadProgress[pf.id].message ? `：${uploadProgress[pf.id].message}` : ''}
                            </span>
                        )}
                                <button
                                    type="button"
                                    className="remove-btn"
                                    onClick={() => removeFile(pf.id)}
                                    disabled={isUploading}
                                >
                                    移除
                                </button>
                            </div>
                    </li>
                ))}
            </ul>
            </div>
        </div>
    );
};

export default MultiFileUpload;