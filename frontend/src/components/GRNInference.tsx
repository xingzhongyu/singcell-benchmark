import React, { useState } from 'react';
import { inferGRN, inferGRNWithGRNBoost2, inferGRNWithCEFCON, inferGRNWithScDGRN } from '../services/api';
import { DeepSEMParameters, GRNEdge, GRNInferenceResults, ScDGRNInferenceResults } from '../types';
import GRNVisualization from './GRNVisualization';
import './GRNInference.css';

interface GRNInferenceProps {
  onResultsReady?: (results: GRNInferenceResults) => void;
}

type AlgorithmType = 'deepsem' | 'grnboost2' | 'genie3' | 'cefcon' | 'scdgrn';

const GRNInference: React.FC<GRNInferenceProps> = ({ onResultsReady }) => {
  const [algorithm, setAlgorithm] = useState<AlgorithmType>('deepsem');
  const [expressionFile, setExpressionFile] = useState<File | null>(null);
  const [networkFile, setNetworkFile] = useState<File | null>(null);
  const [tfFile, setTfFile] = useState<File | null>(null);
  const [expressionZip, setExpressionZip] = useState<File | null>(null);
  const [scdgrnResults, setScdgrnResults] = useState<ScDGRNInferenceResults | null>(null);
  const [selectedTimePoint, setSelectedTimePoint] = useState<string>('');
  const [parameters, setParameters] = useState<DeepSEMParameters>({
    task: 'celltype_GRN',
    setting: 'default',
    n_epochs: 120,
    batch_size: 64,
    alpha: 100.0,
    beta: 1.0,
    lr: 1e-4,
    n_hidden: 128,
    K: 1,
    K1: 1,
    K2: 2,
    gamma: 0.95,
    lr_step_size: 0.99,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<GRNInferenceResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExpressionFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setExpressionFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleNetworkFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setNetworkFile(e.target.files[0]);
    }
  };

  const handleTfFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setTfFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleExpressionZipChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setExpressionZip(e.target.files[0]);
      setError(null);
    }
  };

  const handleParameterChange = (key: keyof DeepSEMParameters, value: any) => {
    setParameters(prev => ({
      ...prev,
      [key]: typeof prev[key] === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleRunInference = async () => {
    // scDGRN 需要 ZIP 文件
    if (algorithm === 'scdgrn') {
      if (!expressionZip) {
        setError('请选择包含6个时间点CSV文件的ZIP压缩包');
        return;
      }
    } else {
      if (!expressionFile) {
        setError('请选择基因表达矩阵文件');
        return;
      }

      // GRNBoost2/Genie3 需要转录因子文件
      if ((algorithm === 'grnboost2' || algorithm === 'genie3') && !tfFile) {
        setError('请选择转录因子列表文件');
        return;
      }
    }

    setIsRunning(true);
    setError(null);
    setResults(null);
    setScdgrnResults(null);
    setSelectedTimePoint('');

    try {
      if (algorithm === 'scdgrn') {
        // scDGRN 返回多个时间点的结果
        const timePointResults = await inferGRNWithScDGRN(expressionZip!);
        const timePoints = Object.keys(timePointResults).sort();
        const firstTimePoint = timePoints[0] || '';
        
        setScdgrnResults({
          timePoints: timePointResults,
          selectedTimePoint: firstTimePoint
        });
        setSelectedTimePoint(firstTimePoint);
        
        // 显示第一个时间点的结果
        if (firstTimePoint && timePointResults[firstTimePoint]) {
          const edges = timePointResults[firstTimePoint];
          const nodeSet = new Set<string>();
          edges.forEach(edge => {
            nodeSet.add(edge.source);
            nodeSet.add(edge.target);
          });

          const inferenceResults: GRNInferenceResults = {
            edges,
            nodeCount: nodeSet.size,
            edgeCount: edges.length,
          };

          setResults(inferenceResults);
          if (onResultsReady) {
            onResultsReady(inferenceResults);
          }
        }
      } else {
        let edges: GRNEdge[];
        
        if (algorithm === 'deepsem') {
          edges = await inferGRN(expressionFile!, networkFile, parameters);
        } else if (algorithm === 'cefcon') {
          // CEFCON
          edges = await inferGRNWithCEFCON(expressionFile!);
        } else {
          // GRNBoost2 或 Genie3
          const algo = algorithm === 'grnboost2' ? 'grnboost2' : 'genie3';
          edges = await inferGRNWithGRNBoost2(expressionFile!, tfFile!, algo);
        }
        
        // 计算节点和边的统计信息
        const nodeSet = new Set<string>();
        edges.forEach(edge => {
          nodeSet.add(edge.source);
          nodeSet.add(edge.target);
        });

        const inferenceResults: GRNInferenceResults = {
          edges,
          nodeCount: nodeSet.size,
          edgeCount: edges.length,
        };

        setResults(inferenceResults);
        if (onResultsReady) {
          onResultsReady(inferenceResults);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '推断失败');
    } finally {
      setIsRunning(false);
    }
  };

  const handleTimePointChange = (timePoint: string) => {
    if (!scdgrnResults || !scdgrnResults.timePoints[timePoint]) return;
    
    setSelectedTimePoint(timePoint);
    const edges = scdgrnResults.timePoints[timePoint];
    const nodeSet = new Set<string>();
    edges.forEach(edge => {
      nodeSet.add(edge.source);
      nodeSet.add(edge.target);
    });

    const inferenceResults: GRNInferenceResults = {
      edges,
      nodeCount: nodeSet.size,
      edgeCount: edges.length,
    };

    setResults(inferenceResults);
    if (onResultsReady) {
      onResultsReady(inferenceResults);
    }
  };

  const handleNodeSelect = (nodeId: string) => {
    console.log('Selected node:', nodeId);
    // 可以在这里添加节点详情显示逻辑
  };

  // 下载 CSV 文件
  const handleDownloadCSV = () => {
    if (!results) return;

    // CSV 转义函数，处理包含逗号、引号或换行符的字段
    const escapeCSV = (field: string): string => {
      if (field.includes(',') || field.includes('"') || field.includes('\n')) {
        return `"${field.replace(/"/g, '""')}"`;
      }
      return field;
    };

    // 将边列表转换为 CSV 格式
    const csvRows = [
      ['source', 'target', 'weight'], // 表头
      ...results.edges.map(edge => [
        escapeCSV(edge.source),
        escapeCSV(edge.target),
        edge.weight.toString()
      ])
    ];

    // 转换为 CSV 字符串（添加 BOM 以支持 Excel 正确识别 UTF-8）
    const csvContent = '\uFEFF' + csvRows.map(row => row.join(',')).join('\n');

    // 创建 Blob 并下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const timestamp = new Date().toISOString().split('T')[0];
    const timePointSuffix = selectedTimePoint ? `_${selectedTimePoint}` : '';
    link.download = `grn_results_${timestamp}${timePointSuffix}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 下载所有时间点的 CSV 文件（仅 scDGRN）
  const handleDownloadAllTimePoints = () => {
    if (!scdgrnResults) return;

    Object.keys(scdgrnResults.timePoints).forEach(timePoint => {
      const edges = scdgrnResults.timePoints[timePoint];
      const escapeCSV = (field: string): string => {
        if (field.includes(',') || field.includes('"') || field.includes('\n')) {
          return `"${field.replace(/"/g, '""')}"`;
        }
        return field;
      };

      const csvRows = [
        ['source', 'target', 'weight'],
        ...edges.map(edge => [
          escapeCSV(edge.source),
          escapeCSV(edge.target),
          edge.weight.toString()
        ])
      ];

      const csvContent = '\uFEFF' + csvRows.map(row => row.join(',')).join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().split('T')[0];
      link.download = `scdgrn_results_${timePoint}_${timestamp}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    });
  };

  return (
    <div className="grn-inference-container">
      <div className="grn-inference-header">
        <h3>基因调控网络推断</h3>
        <p>选择算法并上传文件，推断基因调控网络</p>
      </div>

      <div className="grn-inference-content">
        <div className="grn-inference-form">
          <div className="form-section">
            <h4>算法选择</h4>
            <div className="form-group">
              <label>
                算法:
                <select
                  value={algorithm}
                  onChange={(e) => {
                    setAlgorithm(e.target.value as AlgorithmType);
                    setError(null);
                    setResults(null);
                    setScdgrnResults(null);
                    setSelectedTimePoint('');
                    setExpressionZip(null);
                  }}
                  disabled={isRunning}
                >
                  <option value="deepsem">DeepSEM</option>
                  <option value="grnboost2">GRNBoost2</option>
                  <option value="genie3">Genie3</option>
                  <option value="cefcon">CEFCON</option>
                  <option value="scdgrn">scDGRN</option>
                </select>
              </label>
            </div>
            {algorithm === 'deepsem' && (
              <p className="algorithm-description">
                DeepSEM: 基于变分自编码器的深度学习方法，支持细胞类型特异性和非特异性 GRN 推断
              </p>
            )}
            {(algorithm === 'grnboost2' || algorithm === 'genie3') && (
              <p className="algorithm-description">
                {algorithm === 'grnboost2' ? 'GRNBoost2' : 'Genie3'}: 基于随机森林的算法，需要提供转录因子列表
              </p>
            )}
            {algorithm === 'cefcon' && (
              <p className="algorithm-description">
                CEFCON: 基于图神经网络的谱系特异性基因调控网络推断方法，使用先验网络信息
              </p>
            )}
            {algorithm === 'scdgrn' && (
              <p className="algorithm-description">
                scDGRN: 动态基因调控网络推断方法，需要上传包含6个时间点基因表达数据的ZIP压缩包
              </p>
            )}
          </div>

          <div className="form-section">
            <h4>文件上传</h4>
            {algorithm === 'scdgrn' ? (
              <div className="file-upload-group">
                <label>
                  时间序列基因表达数据 (ZIP) <span className="required">*</span>
                  <input
                    type="file"
                    accept=".zip"
                    onChange={handleExpressionZipChange}
                    disabled={isRunning}
                  />
                  {expressionZip && (
                    <span className="file-name">{expressionZip.name}</span>
                  )}
                </label>
                <p className="file-hint">
                  ZIP 压缩包应包含 6 个按时间顺序命名的 CSV 文件，每个文件为对应时间点的基因表达矩阵
                </p>
              </div>
            ) : (
              <div className="file-upload-group">
                <label>
                  基因表达矩阵 (CSV) <span className="required">*</span>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleExpressionFileChange}
                    disabled={isRunning}
                  />
                  {expressionFile && (
                    <span className="file-name">{expressionFile.name}</span>
                  )}
                </label>
              </div>
            )}
            {algorithm === 'deepsem' && (
              <div className="file-upload-group">
                <label>
                  先验网络结构 (CSV, 可选)
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleNetworkFileChange}
                    disabled={isRunning}
                  />
                  {networkFile && (
                    <span className="file-name">{networkFile.name}</span>
                  )}
                </label>
              </div>
            )}
            {(algorithm === 'grnboost2' || algorithm === 'genie3') && (
              <div className="file-upload-group">
                <label>
                  转录因子列表 (CSV) <span className="required">*</span>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleTfFileChange}
                    disabled={isRunning}
                  />
                  {tfFile && (
                    <span className="file-name">{tfFile.name}</span>
                  )}
                </label>
                <p className="file-hint">单列 CSV 文件，无表头，每行一个转录因子名称</p>
              </div>
            )}
            {algorithm === 'cefcon' && (
              <p className="file-hint" style={{ marginTop: '10px', color: '#28a745' }}>
                CEFCON 使用内置的先验网络，只需上传基因表达矩阵即可
              </p>
            )}
          </div>

          {algorithm === 'deepsem' && (
            <>
          <div className="form-section">
            <h4>任务类型</h4>
            <div className="form-group">
              <label>
                任务类型:
                <select
                  value={parameters.task}
                  onChange={(e) => handleParameterChange('task', e.target.value)}
                  disabled={isRunning}
                >
                  <option value="celltype_GRN">细胞类型特异性 GRN</option>
                  <option value="non_celltype_GRN">非细胞类型特异性 GRN</option>
                  <option value="simulation">模拟</option>
                  <option value="embedding">嵌入</option>
                </select>
              </label>
            </div>
            <div className="form-group">
              <label>
                设置:
                <select
                  value={parameters.setting}
                  onChange={(e) => handleParameterChange('setting', e.target.value)}
                  disabled={isRunning}
                >
                  <option value="default">默认</option>
                  <option value="test">测试</option>
                </select>
              </label>
            </div>
          </div>

          <div className="form-section">
            <h4>超参数 (高级)</h4>
            <div className="form-grid">
              <div className="form-group">
                <label>
                  Epochs:
                  <input
                    type="number"
                    value={parameters.n_epochs}
                    onChange={(e) => handleParameterChange('n_epochs', e.target.value)}
                    disabled={isRunning}
                    min="1"
                  />
                </label>
              </div>
              <div className="form-group">
                <label>
                  Batch Size:
                  <input
                    type="number"
                    value={parameters.batch_size}
                    onChange={(e) => handleParameterChange('batch_size', e.target.value)}
                    disabled={isRunning}
                    min="1"
                  />
                </label>
              </div>
              <div className="form-group">
                <label>
                  Alpha:
                  <input
                    type="number"
                    step="0.1"
                    value={parameters.alpha}
                    onChange={(e) => handleParameterChange('alpha', e.target.value)}
                    disabled={isRunning}
                    min="0"
                  />
                </label>
              </div>
              <div className="form-group">
                <label>
                  Beta:
                  <input
                    type="number"
                    step="0.01"
                    value={parameters.beta}
                    onChange={(e) => handleParameterChange('beta', e.target.value)}
                    disabled={isRunning}
                    min="0"
                  />
                </label>
              </div>
              <div className="form-group">
                <label>
                  Learning Rate:
                  <input
                    type="number"
                    step="1e-5"
                    value={parameters.lr}
                    onChange={(e) => handleParameterChange('lr', e.target.value)}
                    disabled={isRunning}
                    min="0"
                  />
                </label>
              </div>
              <div className="form-group">
                <label>
                  Hidden Units:
                  <input
                    type="number"
                    value={parameters.n_hidden}
                    onChange={(e) => handleParameterChange('n_hidden', e.target.value)}
                    disabled={isRunning}
                    min="1"
                  />
                </label>
              </div>
            </div>
          </div>
            </>
          )}

          <div className="form-actions">
            <button
              onClick={handleRunInference}
              disabled={isRunning || (algorithm === 'scdgrn' ? !expressionZip : !expressionFile)}
              className="run-button"
            >
              {isRunning ? '推断中...' : '开始推断'}
            </button>
            {isRunning && algorithm === 'scdgrn' && (
              <p className="algorithm-description" style={{ marginTop: '10px', color: '#ff9800' }}>
                注意: scDGRN 需要训练模型，可能需要较长时间（数分钟到数十分钟），请耐心等待...
              </p>
            )}
          </div>

          {error && (
            <div className="error-message">
              <strong>错误:</strong> {error}
            </div>
          )}
        </div>

        {results && (
          <div className="grn-results">
            <div className="results-header">
              <h4>推断结果</h4>
              <div className="results-header-actions">
                {scdgrnResults && (
                  <div className="timepoint-selector" style={{ marginRight: '10px' }}>
                    <label>
                      时间点:
                      <select
                        value={selectedTimePoint}
                        onChange={(e) => handleTimePointChange(e.target.value)}
                        style={{ marginLeft: '5px', padding: '5px' }}
                      >
                        {Object.keys(scdgrnResults.timePoints).sort().map(tp => (
                          <option key={tp} value={tp}>{tp}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
                <button
                  onClick={handleDownloadCSV}
                  className="download-button"
                  title="下载当前时间点的 CSV 文件"
                >
                  📥 下载 CSV
                </button>
                {scdgrnResults && (
                  <button
                    onClick={handleDownloadAllTimePoints}
                    className="download-button"
                    title="下载所有时间点的 CSV 文件"
                    style={{ marginLeft: '10px' }}
                  >
                    📥 下载全部时间点
                  </button>
                )}
                <div className="results-stats">
                  <span>节点数: {results.nodeCount}</span>
                  <span>边数: {results.edgeCount}</span>
                </div>
              </div>
            </div>
            <GRNVisualization
              edges={results.edges}
              onNodeSelect={handleNodeSelect}
              height={600}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default GRNInference;

