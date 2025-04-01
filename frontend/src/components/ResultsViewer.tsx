import React from 'react';
import { AppDatasetState, AnalysisResultsSummary, IntegrationResultsSummary, TrajectoryResultsSummary, CellCommunicationResultsSummary } from '../types';
import {
    getUmapPlotUrl, getQCViolinPlotUrl, getProcessedDataUrl, getMarkerGenesUrl,
    getIntegratedUmapPlotUrl, getIntegratedDataUrl,
    getDiffmapPlotUrl, getPagaPlotUrl, getDptUmapPlotUrl,
    getCellPhoneDbPlotUrl, getCellPhoneDbDownloadUrl
 } from '../services/api';
 import Plot from 'react-plotly.js'; // Import if needed for interactive plots
 // import MarkerGeneTable from './MarkerGeneTable'; // Example sub-component
 // import GeneExpressionPlot from './GeneExpressionPlot'; // Example sub-component
 // import './styles.css';

interface ResultsViewerProps {
    dataset: AppDatasetState;
}

// Helper to check if analysis was successful
const wasSuccessful = (status: AppDatasetState['basicAnalysis'] | AppDatasetState['integrationAnalysis'] | AppDatasetState['trajectoryAnalysis'] | AppDatasetState['communicationAnalysis']) => {
    return status?.status?.status === 'SUCCESS';
};

const ResultsViewer: React.FC<ResultsViewerProps> = ({ dataset }) => {

    const basicResults = dataset.basicAnalysis?.resultsSummary as AnalysisResultsSummary | undefined;
    const integrationResults = dataset.integrationAnalysis?.resultsSummary as IntegrationResultsSummary | undefined;
    const trajectoryResults = dataset.trajectoryAnalysis?.resultsSummary as TrajectoryResultsSummary | undefined;
    const commResults = dataset.communicationAnalysis?.resultsSummary as CellCommunicationResultsSummary | undefined;

    const clusterMethod = dataset.basicAnalysis?.parameters?.clustering_method || 'leiden'; // Get method used

    return (
        <div className="results-viewer">
            <h4>Dataset Information</h4>
            <ul>
                <li>Data ID: {dataset.dataId}</li>
                <li>Type: {dataset.isIntegrated ? `Integrated (Sources: ${dataset.sourceDataIds?.join(', ') || 'N/A'})` : `Original (${dataset.filename || 'N/A'})`}</li>
                {/* Add more base info */}
            </ul>

             {/* --- Integration Results (if applicable) --- */}
             {dataset.isIntegrated && wasSuccessful(dataset.integrationAnalysis) && integrationResults && (
                 <div className="result-section">
                     <h5>Integration Results ({integrationResults.integration_method})</h5>
                     {integrationResults.umap_batch_plot_path && (
                        <img src={getIntegratedUmapPlotUrl(dataset.dataId, 'batch')} alt="Integrated UMAP by Batch" className="result-plot" />
                     )}
                      {/* Add integrated cluster plot if generated */}
                      {integrationResults.integrated_data_path && (
                        <p><a href={getIntegratedDataUrl(dataset.dataId)} download={`${dataset.dataId}_integrated.h5ad`}>Download Integrated Data</a></p>
                      )}
                     {/* Display other integration summary info */}
                 </div>
             )}

            {/* --- Basic Analysis Results --- */}
            {wasSuccessful(dataset.basicAnalysis) && basicResults && (
                <div className="result-section">
                    <h5>Basic Analysis Results</h5>
                    {basicResults.qc_plot_path && (
                        <img src={getQCViolinPlotUrl(dataset.dataId)} alt="QC Violin Plot" className="result-plot" />
                    )}
                    {basicResults.umap_plot_path && (
                        <img src={getUmapPlotUrl(dataset.dataId, clusterMethod)} alt={`UMAP by ${clusterMethod}`} className="result-plot" />
                    )}
                    {/* Add Marker Gene Table display here (maybe own component) */}
                    {/* Add Gene Expression Plot component here */}
                    {basicResults.processed_data_path && (
                         <p><a href={getProcessedDataUrl(dataset.dataId)} download={`${dataset.dataId}_processed.h5ad`}>Download Processed Data</a></p>
                    )}
                     {basicResults.marker_genes_path && (
                         <p><a href={getMarkerGenesUrl(dataset.dataId, clusterMethod, 'csv')} download={`marker_genes_${clusterMethod}.csv`}>Download Marker Genes (CSV)</a></p>
                     )}
                </div>
            )}


            {/* --- Trajectory Analysis Results --- */}
             {wasSuccessful(dataset.trajectoryAnalysis) && trajectoryResults && (
                <div className="result-section">
                    <h5>Trajectory Analysis Results</h5>
                     {trajectoryResults.diffmap_plot_path && (
                        <img src={getDiffmapPlotUrl(dataset.dataId)} alt="Diffusion Map" className="result-plot" />
                     )}
                      {trajectoryResults.paga_graph_plot_path && (
                        <img src={getPagaPlotUrl(dataset.dataId, 'graph')} alt="PAGA Graph" className="result-plot" />
                     )}
                       {trajectoryResults.paga_umap_plot_path && (
                        <img src={getPagaPlotUrl(dataset.dataId, 'umap_embedding')} alt="PAGA on UMAP" className="result-plot" />
                     )}
                        {trajectoryResults.dpt_umap_plot_path && (
                        <img src={getDptUmapPlotUrl(dataset.dataId)} alt="UMAP colored by DPT" className="result-plot" />
                     )}
                     {/* Display other trajectory info */}
                </div>
             )}


             {/* --- Cell Communication Results --- */}
             {wasSuccessful(dataset.communicationAnalysis) && commResults && (
                <div className="result-section">
                     <h5>Cell Communication Results (CellPhoneDB)</h5>
                     {commResults.cpdb_output_dir && (
                         <p><a href={getCellPhoneDbDownloadUrl(dataset.dataId)} download={`${dataset.dataId}_cellphonedb_results.zip`}>Download CellPhoneDB Results (.zip)</a></p>
                     )}
                     <p><i>Plots for CellPhoneDB need specific implementation based on output files.</i></p>
                     {/* Example: If dot_plot.png is generated by backend task */}
                     {/* <img src={getCellPhoneDbPlotUrl(dataset.dataId, 'dot_plot.png')} alt="CellPhoneDB Dot Plot" /> */}
                     {/* Display stdout/stderr if needed for debugging? */}
                     {/* {commResults.cellphonedb_stderr && <pre>Stderr: {commResults.cellphonedb_stderr}</pre>} */}
                </div>
             )}

            {/* Message if no results are available yet */}
             {!wasSuccessful(dataset.basicAnalysis) && !wasSuccessful(dataset.integrationAnalysis) && (
                 <p>No analysis results available for this dataset yet. Run an analysis from Section 2.</p>
             )}

        </div>
    );
};

export default ResultsViewer;