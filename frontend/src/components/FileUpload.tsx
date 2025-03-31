import React, { useState, useCallback } from 'react';
import { uploadFile } from '../services/api';
import { UploadResponse } from '../types';

interface FileUploadProps {
  onUploadSuccess: (response: UploadResponse) => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      if (file.name.endsWith('.h5ad')) {
          setSelectedFile(file);
          setError(null); // Clear previous errors
          setUploadResponse(null); // Clear previous response
      } else {
          setSelectedFile(null);
          setError("Please select a .h5ad file.");
      }
    }
  };

  const handleUpload = useCallback(async () => {
    if (!selectedFile) {
      setError("No file selected.");
      return;
    }

    setUploading(true);
    setError(null);
    setUploadResponse(null);

    try {
      const response = await uploadFile(selectedFile);
      setUploadResponse(response);
      onUploadSuccess(response); // Notify parent component
    } catch (err: any) {
      setError(err.message || "Upload failed.");
      console.error(err);
    } finally {
      setUploading(false);
    }
  }, [selectedFile, onUploadSuccess]);

  return (
    <div>
      <h3>1. Upload Data</h3>
      <input type="file" accept=".h5ad" onChange={handleFileChange} disabled={uploading} />
      <button onClick={handleUpload} disabled={!selectedFile || uploading}>
        {uploading ? 'Uploading...' : 'Upload H5AD'}
      </button>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {uploadResponse && (
        <p style={{ color: 'green' }}>
          Uploaded: {uploadResponse.filename} (ID: {uploadResponse.data_id})
        </p>
      )}
    </div>
  );
};

export default FileUpload;