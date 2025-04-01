import React, { useState, ChangeEvent } from 'react';
// import './styles.css'; // Optional styling

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
            <label htmlFor="file-input" className="file-input-label">
                Select .h5ad Files
            </label>
            <input
                id="file-input"
                type="file"
                accept=".h5ad"
                multiple
                onChange={handleFileChange}
                disabled={isUploading}
                style={{ display: 'none' }} // Hide default input, style the label
            />
             <p>Prepare files for upload (assign batch labels):</p>
            {preparedFiles.length === 0 && !isUploading && <p>No files selected.</p>}
            <ul>
                {preparedFiles.map((pf) => (
                    <li key={pf.id}>
                        <span>{pf.file.name}</span>
                        <input
                            type="text"
                            value={pf.batchLabel}
                            onChange={(e) => handleLabelChange(pf.id, e.target.value)}
                            placeholder="Batch Label"
                            disabled={isUploading || uploadProgress[pf.id]?.status === 'success'}
                            style={{ marginLeft: '10px', marginRight: '10px' }}
                        />
                        <button onClick={() => removeFile(pf.id)} disabled={isUploading}>Remove</button>
                        {uploadProgress[pf.id] && (
                            <span className={`upload-status-${uploadProgress[pf.id].status}`} style={{ marginLeft: '10px' }}>
                                {uploadProgress[pf.id].status} {uploadProgress[pf.id].message || ''}
                            </span>
                        )}
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default MultiFileUpload;