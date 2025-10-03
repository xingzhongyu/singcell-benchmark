import React from 'react';
import { AppDatasetState, AnalysisResultsSummary, IntegrationResultsSummary, TrajectoryResultsSummary, CellCommunicationResultsSummary, RnaVelocityResultsSummary, AtacAnalysisResultsSummary } from '../types'; // Ensure RnaVelocityResultsSummary is imported
import {
    // ... existing imports ...
    getVelocityPlotUrl, getVelocityDataUrl, // Add velocity URL getters
    getIntegratedUmapPlotUrl,
    getIntegratedDataUrl,
    getQCViolinPlotUrl,
    getUmapPlotUrl,
    getProcessedDataUrl,
    getMarkerGenesUrl,
    getDiffmapPlotUrl,
    getPagaPlotUrl,
    getDptUmapPlotUrl,
    getCellPhoneDbDownloadUrl,
    getAtacQcPlotUrl,
    getAtacUmapPlotUrl,
    getProcessedAtacDataUrl
 } from '../services/api';
// import Plot from 'react-plotly.js'; // If needed later
import './styles.css';

interface ResultsViewerProps {
    dataset: AppDatasetState;
}

const wasSuccessful = (status: AppDatasetState[keyof AppDatasetState]) => {
    // Check if status exists and is SUCCESS
    return status && typeof status === 'object' && 'status' in status && status.status?.status === 'SUCCESS';
};


const ResultsViewer: React.FC<ResultsViewerProps> = ({ dataset }) => {
    // Use type assertion for potentially undefined results
    const basicResults = dataset.basicAnalysis?.resultsSummary as AnalysisResultsSummary | undefined;
    const integrationResults = dataset.integrationAnalysis?.resultsSummary as IntegrationResultsSummary | undefined;
    const trajectoryResults = dataset.trajectoryAnalysis?.resultsSummary as TrajectoryResultsSummary | undefined;
    const commResults = dataset.communicationAnalysis?.resultsSummary as CellCommunicationResultsSummary | undefined;
    const velocityResults = dataset.velocityAnalysis?.resultsSummary as RnaVelocityResultsSummary | undefined; // Get velocity results

    // Determine cluster method used if basic analysis ran
    const clusterMethod = dataset.basicAnalysis?.parameters?.clustering_method || 'leiden';
    // Determine velocity basis used if velocity analysis ran
    const velocityBasis = dataset.velocityAnalysis?.parameters?.embedding_basis || 'umap';
    const atacResults = dataset.atacAnalysis?.resultsSummary as AtacAnalysisResultsSummary | undefined;
    const atacColorKey = atacResults?.clustering_done ? 'clusters' : undefined; // Default to clusters if available

    return (
        <div className="results-viewer">
            <h4>Dataset Information</h4>
            {/* ... Dataset Info list ... */}

             {/* --- Integration Results --- */}
             {dataset.isIntegrated && wasSuccessful(dataset.integrationAnalysis) && integrationResults && (
                 <div className="result-section">
                     <h5>Integration Results ({integrationResults.integration_method})</h5>
                     {integrationResults.umap_batch_plot_path && (
                        <img src={getIntegratedUmapPlotUrl(dataset.dataId, 'batch')} alt="Integrated UMAP by Batch" className="result-plot" />
                     )}
                      {/* Add integrated cluster plot if generated */}
                      {integrationResults.integrated_data_path && (
                        <p><a href={getIntegratedDataUrl(dataset.dataId)} download={`${dataset.dataId}.h5ad`}>Download Integrated Data</a></p>
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

             {/* --- RNA Velocity Results --- */}
             {wasSuccessful(dataset.velocityAnalysis) && velocityResults && (
                <div className="result-section">
                     <h5>RNA Velocity Results (Mode: {velocityResults.velocity_calculated?.mode || 'N/A'})</h5>
                      {!velocityResults.embedding_basis_found && <p><i>Warning: Embedding basis ('{velocityBasis}') not found in processed data; plots may be missing.</i></p>}
                      {velocityResults.grid_plot_path && (
                        <img src={getVelocityPlotUrl(dataset.dataId, velocityBasis, 'grid')} alt={`Velocity Grid (${velocityBasis})`} className="result-plot" />
                     )}
                       {velocityResults.stream_plot_path && (
                        <img src={getVelocityPlotUrl(dataset.dataId, velocityBasis, 'stream')} alt={`Velocity Stream (${velocityBasis})`} className="result-plot" />
                     )}
                      {velocityResults.updated_adata_path && (
                         <p><a href={getVelocityDataUrl(dataset.dataId)} download={`${dataset.dataId}_velocity.h5ad`}>Download Data w/ Velocity</a></p>
                      )}
                      {!velocityResults.grid_plot_path && !velocityResults.stream_plot_path && velocityResults.velocity_calculated && <p>Velocity calculated, but plots could not be generated (check embedding basis).</p>}
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
            {!wasSuccessful(dataset.basicAnalysis) && !wasSuccessful(dataset.integrationAnalysis) && !wasSuccessful(dataset.velocityAnalysis) && (
                 <p>No analysis results available for this dataset yet. Run an analysis from Section 2.</p>
             )}
            {/* --- ATAC Analysis Results --- */}
            {wasSuccessful(dataset.atacAnalysis) && atacResults && (
                <div className="result-section">
                    <h5>ATAC Analysis Results</h5>
                    {atacResults.qc_plot_path && (
                        <img src={getAtacQcPlotUrl(dataset.dataId)} alt="ATAC QC Violin Plot" className="result-plot" />
                    )}
                    {atacResults.umap_cluster_plot_path && atacColorKey && ( // Use the specific path if available
                        <img src={getAtacUmapPlotUrl(dataset.dataId, atacColorKey)} alt={`ATAC UMAP (${atacColorKey})`} className="result-plot" />
                    )}
                     {!atacResults.umap_cluster_plot_path && atacResults.umap_done && <p>ATAC UMAP plot generated but coloring by cluster might have failed.</p>}
                     {!atacResults.umap_done && <p>ATAC UMAP was not calculated or failed.</p>}

                    {atacResults.processed_adata_path && (
                        <p><a href={getProcessedAtacDataUrl(dataset.dataId)} download={`${dataset.dataId}_processed_atac.h5ad`}>Download Processed ATAC Data</a></p>
                    )}
                    {/* Display other summary info like shapes, LSI components used */}
                    <ul>
                         {atacResults.initial_shape && <li>Initial Shape: {atacResults.initial_shape.obs} cells x {atacResults.initial_shape.var} features</li>}
                         {atacResults.shape_after_filtering && <li>Shape after Filtering: {atacResults.shape_after_filtering.obs} x {atacResults.shape_after_filtering.var}</li>}
                         {atacResults.lsi_done && <li>LSI Components Used: {atacResults.lsi_done.n_components_used}</li>}
                    </ul>
                </div>
            )}

            {/* ... No results message ... */}
        </div>
    );
};

export default ResultsViewer;