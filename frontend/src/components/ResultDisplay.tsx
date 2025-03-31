import React from 'react';
import { getUmapPlotUrl } from '../services/api';

interface ResultDisplayProps {
  dataId: string | null;
  analysisComplete: boolean;
}

const ResultDisplay: React.FC<ResultDisplayProps> = ({ dataId, analysisComplete }) => {
  if (!dataId || !analysisComplete) {
    return <div></div>; // Don't show anything until analysis is done
  }

  const umapUrl = getUmapPlotUrl(dataId);

  return (
    <div>
      <h3>3. Results</h3>
      <h4>UMAP Plot (colored by Leiden clusters)</h4>
      <img
        src={umapUrl}
        alt="UMAP Plot"
        style={{ maxWidth: '600px', height: 'auto', border: '1px solid #ccc' }}
        // Optional: Add error handling for image loading
        onError={(e) => {
            console.error("Failed to load UMAP image");
            (e.target as HTMLImageElement).alt = "Failed to load UMAP plot";
            // Optionally display an error message or placeholder
            (e.target as HTMLImageElement).src = ""; // Clear broken image link
        }}
      />
       {/* Add sections for other results later */}
       {/* <p><a href={getProcessedDataUrl(dataId)} download>Download Processed Data (.h5ad)</a></p> */}
    </div>
  );
};

export default ResultDisplay;