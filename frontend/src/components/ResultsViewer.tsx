import React from 'react';
import { AppDatasetState, AnalysisResultsSummary, IntegrationResultsSummary, TrajectoryResultsSummary, CellCommunicationResultsSummary, RnaVelocityResultsSummary, AtacAnalysisResultsSummary } from '../types';
import {
    getVelocityPlotUrl, getVelocityDataUrl,
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
import './ResultsViewer.css';

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
            <div className="results-card">
                <div className="results-header">
                    <div>
                        <h4>分析结果</h4>
                        <p>各分析项结果按模块展示，包含可下载文件与图表。</p>
                    </div>
                </div>

                {/* --- Integration Results --- */}
                {dataset.isIntegrated && wasSuccessful(dataset.integrationAnalysis) && integrationResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>整合结果（{integrationResults.integration_method}）</h5>
                            <div className="section-actions">
                                {integrationResults.integrated_data_path && (
                                    <a className="ghost-link" href={getIntegratedDataUrl(dataset.dataId)} download={`${dataset.dataId}.h5ad`}>
                                        下载整合数据
                                    </a>
                                )}
                            </div>
                        </div>
                        {integrationResults.umap_batch_plot_path && (
                            <img src={getIntegratedUmapPlotUrl(dataset.dataId, 'batch')} alt="Integrated UMAP by Batch" className="result-plot" />
                        )}
                    </div>
                )}

                {/* --- Basic Analysis Results --- */}
                {wasSuccessful(dataset.basicAnalysis) && basicResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>基础分析结果</h5>
                            <div className="section-actions">
                                {basicResults.processed_data_path && (
                                    <a className="ghost-link" href={getProcessedDataUrl(dataset.dataId)} download={`${dataset.dataId}_processed.h5ad`}>
                                        下载处理后数据
                                    </a>
                                )}
                                {basicResults.marker_genes_path && (
                                    <a className="ghost-link" href={getMarkerGenesUrl(dataset.dataId, clusterMethod, 'csv')} download={`marker_genes_${clusterMethod}.csv`}>
                                        下载 Marker 基因
                                    </a>
                                )}
                            </div>
                        </div>
                        <div className="plot-grid">
                            {basicResults.qc_plot_path && (
                                <div className="plot-item">
                                    <img src={getQCViolinPlotUrl(dataset.dataId)} alt="QC Violin Plot" className="result-plot" />
                                    <span className="plot-caption">QC Violin</span>
                                </div>
                            )}
                            {basicResults.umap_plot_path && (
                                <div className="plot-item">
                                    <img src={getUmapPlotUrl(dataset.dataId, clusterMethod)} alt={`UMAP by ${clusterMethod}`} className="result-plot" />
                                    <span className="plot-caption">UMAP ({clusterMethod})</span>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* --- RNA Velocity Results --- */}
                {wasSuccessful(dataset.velocityAnalysis) && velocityResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>RNA Velocity（模式：{velocityResults.velocity_calculated?.mode || 'N/A'}）</h5>
                            <div className="section-actions">
                                {velocityResults.updated_adata_path && (
                                    <a className="ghost-link" href={getVelocityDataUrl(dataset.dataId)} download={`${dataset.dataId}_velocity.h5ad`}>
                                        下载含 Velocity 的数据
                                    </a>
                                )}
                            </div>
                        </div>
                        {!velocityResults.embedding_basis_found && (
                            <p className="hint-text">警告：未找到嵌入基准 '{velocityBasis}'，可能缺少相关图表。</p>
                        )}
                        <div className="plot-grid">
                            {velocityResults.grid_plot_path && (
                                <div className="plot-item">
                                    <img src={getVelocityPlotUrl(dataset.dataId, velocityBasis, 'grid')} alt={`Velocity Grid (${velocityBasis})`} className="result-plot" />
                                    <span className="plot-caption">Grid Plot</span>
                                </div>
                            )}
                            {velocityResults.stream_plot_path && (
                                <div className="plot-item">
                                    <img src={getVelocityPlotUrl(dataset.dataId, velocityBasis, 'stream')} alt={`Velocity Stream (${velocityBasis})`} className="result-plot" />
                                    <span className="plot-caption">Stream Plot</span>
                                </div>
                            )}
                        </div>
                        {!velocityResults.grid_plot_path && !velocityResults.stream_plot_path && velocityResults.velocity_calculated && (
                            <p className="hint-text">已计算 velocity，但未生成图表（检查嵌入基准）。</p>
                        )}
                    </div>
                )}

                {/* --- Trajectory Analysis Results --- */}
                {wasSuccessful(dataset.trajectoryAnalysis) && trajectoryResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>轨迹分析结果</h5>
                        </div>
                        <div className="plot-grid">
                            {trajectoryResults.diffmap_plot_path && (
                                <div className="plot-item">
                                    <img src={getDiffmapPlotUrl(dataset.dataId)} alt="Diffusion Map" className="result-plot" />
                                    <span className="plot-caption">Diffmap</span>
                                </div>
                            )}
                            {trajectoryResults.paga_graph_plot_path && (
                                <div className="plot-item">
                                    <img src={getPagaPlotUrl(dataset.dataId, 'graph')} alt="PAGA Graph" className="result-plot" />
                                    <span className="plot-caption">PAGA Graph</span>
                                </div>
                            )}
                            {trajectoryResults.paga_umap_plot_path && (
                                <div className="plot-item">
                                    <img src={getPagaPlotUrl(dataset.dataId, 'umap_embedding')} alt="PAGA on UMAP" className="result-plot" />
                                    <span className="plot-caption">PAGA UMAP</span>
                                </div>
                            )}
                            {trajectoryResults.dpt_umap_plot_path && (
                                <div className="plot-item">
                                    <img src={getDptUmapPlotUrl(dataset.dataId)} alt="UMAP colored by DPT" className="result-plot" />
                                    <span className="plot-caption">DPT UMAP</span>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* --- Cell Communication Results --- */}
                {wasSuccessful(dataset.communicationAnalysis) && commResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>细胞通信 (CellPhoneDB)</h5>
                            <div className="section-actions">
                                {commResults.cpdb_output_dir && (
                                    <a className="ghost-link" href={getCellPhoneDbDownloadUrl(dataset.dataId)} download={`${dataset.dataId}_cellphonedb_results.zip`}>
                                        下载结果 (.zip)
                                    </a>
                                )}
                            </div>
                        </div>
                        <p className="hint-text">如需可视化，请根据 CellPhoneDB 输出文件补充相应展示。</p>
                    </div>
                )}

                {/* --- ATAC Analysis Results --- */}
                {wasSuccessful(dataset.atacAnalysis) && atacResults && (
                    <div className="result-section">
                        <div className="section-head">
                            <h5>ATAC 分析结果</h5>
                            <div className="section-actions">
                                {atacResults.processed_adata_path && (
                                    <a className="ghost-link" href={getProcessedAtacDataUrl(dataset.dataId)} download={`${dataset.dataId}_processed_atac.h5ad`}>
                                        下载处理后 ATAC 数据
                                    </a>
                                )}
                            </div>
                        </div>
                        <div className="plot-grid">
                            {atacResults.qc_plot_path && (
                                <div className="plot-item">
                                    <img src={getAtacQcPlotUrl(dataset.dataId)} alt="ATAC QC Violin Plot" className="result-plot" />
                                    <span className="plot-caption">ATAC QC</span>
                                </div>
                            )}
                            {atacResults.umap_cluster_plot_path && atacColorKey && (
                                <div className="plot-item">
                                    <img src={getAtacUmapPlotUrl(dataset.dataId, atacColorKey)} alt={`ATAC UMAP (${atacColorKey})`} className="result-plot" />
                                    <span className="plot-caption">ATAC UMAP</span>
                                </div>
                            )}
                        </div>
                        {!atacResults.umap_cluster_plot_path && atacResults.umap_done && (
                            <p className="hint-text">已生成 UMAP，但按簇上色可能失败。</p>
                        )}
                        {!atacResults.umap_done && (
                            <p className="hint-text">未计算或生成 ATAC UMAP。</p>
                        )}
                        <ul className="meta-list">
                            {atacResults.initial_shape && (
                                <li>初始维度：{atacResults.initial_shape.obs} cells × {atacResults.initial_shape.var} features</li>
                            )}
                            {atacResults.shape_after_filtering && (
                                <li>过滤后维度：{atacResults.shape_after_filtering.obs} × {atacResults.shape_after_filtering.var}</li>
                            )}
                            {atacResults.lsi_done && (
                                <li>LSI 组件数：{atacResults.lsi_done.n_components_used}</li>
                            )}
                        </ul>
                    </div>
                )}

                {/* Message if no results are available */}
                {!wasSuccessful(dataset.basicAnalysis) &&
                    !wasSuccessful(dataset.integrationAnalysis) &&
                    !wasSuccessful(dataset.velocityAnalysis) &&
                    !wasSuccessful(dataset.atacAnalysis) &&
                    !wasSuccessful(dataset.communicationAnalysis) &&
                    !wasSuccessful(dataset.trajectoryAnalysis) && (
                        <p className="hint-text">暂未有结果，请在第 2 步运行分析任务。</p>
                    )}
            </div>
        </div>
    );
};

export default ResultsViewer;