import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { GRNEdge } from '../types';
import './GRNVisualization.css';

interface GRNVisualizationProps {
  edges: GRNEdge[];
  onNodeSelect?: (nodeId: string) => void;
  height?: number;
}

const GRNVisualization: React.FC<GRNVisualizationProps> = ({
  edges,
  onNodeSelect,
  height = 600,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [minWeight, setMinWeight] = useState(0);
  const [maxWeight, setMaxWeight] = useState(1);
  const [weightThreshold, setWeightThreshold] = useState(0);
  const [displayMode, setDisplayMode] = useState<'all' | 'top_edges' | 'top_nodes'>('top_edges');
  const [maxElements, setMaxElements] = useState(50); // 默认最多显示 50 个节点或边

  // 筛选和过滤边
  const getFilteredEdges = () => {
    let filtered = edges.filter((edge: GRNEdge) => Math.abs(edge.weight) >= weightThreshold);
    
    if (displayMode === 'top_edges') {
      // 只显示权重最高的边
      filtered = filtered
        .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
        .slice(0, maxElements);
    } else if (displayMode === 'top_nodes') {
      // 计算每个节点的度（连接数）
      const nodeDegree: { [key: string]: number } = {};
      filtered.forEach((edge: GRNEdge) => {
        nodeDegree[edge.source] = (nodeDegree[edge.source] || 0) + Math.abs(edge.weight);
        nodeDegree[edge.target] = (nodeDegree[edge.target] || 0) + Math.abs(edge.weight);
      });
      
      // 选择度最高的节点
      const topNodes = Object.entries(nodeDegree)
        .sort(([, a], [, b]) => b - a)
        .slice(0, maxElements)
        .map(([node]) => node);
      
      const topNodeSet = new Set(topNodes);
      // 只保留连接这些节点的边
      filtered = filtered.filter(
        (edge: GRNEdge) => topNodeSet.has(edge.source) && topNodeSet.has(edge.target)
      );
    }
    // 'all' 模式不进行额外筛选
    
    return filtered;
  };

  // 初始化 Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const filteredEdges = getFilteredEdges();
    
    // 创建节点集合（只包含筛选后的边涉及的节点）
    const nodeSet = new Set<string>();
    filteredEdges.forEach((edge: GRNEdge) => {
      nodeSet.add(edge.source);
      nodeSet.add(edge.target);
    });

    const nodes = Array.from(nodeSet).map(id => ({
      data: { id, label: id },
    }));

    const cyEdges = filteredEdges.map((edge: GRNEdge) => ({
      data: {
        id: `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        weight: edge.weight,
        label: edge.weight.toFixed(4),
      },
    }));

    // 初始化 Cytoscape
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...cyEdges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#61bffc',
            'label': 'data(label)',
            'width': 30,
            'height': 30,
            'font-size': '12px',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-outline-width': 2,
            'text-outline-color': '#ffffff',
            'border-width': 2,
            'border-color': '#4a90e2',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 'mapData(weight, 0, 1, 1, 5)',
            'line-color': '#999',
            'target-arrow-color': '#999',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.5,
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '10px',
            'text-rotation': 'autorotate',
            'text-margin-y': -5,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'background-color': '#ff6b6b',
            'border-width': 3,
            'border-color': '#ff4757',
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#ff6b6b',
            'target-arrow-color': '#ff6b6b',
            'width': 6,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        fit: true,
        padding: 50, // 增加内边距
        directed: true,
        spacingFactor: 2.5, // 增加节点间距
      },
      minZoom: 0.1,
      maxZoom: 4,
    });

    const cy = cyRef.current;

    // 节点点击事件
    if (onNodeSelect) {
      cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
        const node = evt.target;
        onNodeSelect(node.id());
      });
    }

    // 添加工具栏
    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) {
        cy.elements().unselect();
      }
    });

    // 清理函数
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [edges, weightThreshold, displayMode, maxElements, onNodeSelect]);

  // 计算权重范围
  useEffect(() => {
    if (edges.length === 0) return;
    const weights = edges.map((e: GRNEdge) => Math.abs(e.weight));
    setMinWeight(Math.min(...weights));
    setMaxWeight(Math.max(...weights));
    setWeightThreshold(0);
  }, [edges]);

  // 更新布局
  const handleLayoutChange = (layoutName: string) => {
    if (!cyRef.current) return;
    const layouts: { [key: string]: any } = {
      breadthfirst: {
        name: 'breadthfirst',
        fit: true,
        padding: 50,
        directed: true,
        spacingFactor: 2.5,
      },
      grid: {
        name: 'grid',
        fit: true,
        padding: 50,
        rows: undefined,
        cols: undefined,
      },
      circle: {
        name: 'circle',
        fit: true,
        padding: 50,
        radius: undefined,
      },
      concentric: {
        name: 'concentric',
        fit: true,
        padding: 50,
        startAngle: 3 / 2 * Math.PI,
        sweep: undefined,
      },
      random: {
        name: 'random',
        fit: true,
        padding: 50,
      },
    };
    cyRef.current.layout(layouts[layoutName] || layouts.breadthfirst).run();
  };

  // 重置视图
  const handleResetView = () => {
    if (cyRef.current) {
      cyRef.current.fit();
      cyRef.current.center();
    }
  };

  // 导出图片
  const handleExport = (format: 'png' | 'jpg' | 'svg') => {
    if (!cyRef.current) return;
    try {
      if (format === 'png' || format === 'jpg') {
        const dataUrl = cyRef.current.png({ output: 'blob-promise', full: true });
        dataUrl.then((blob: Blob) => {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `grn-network.${format}`;
          link.click();
          URL.revokeObjectURL(url);
        }).catch((err: Error) => {
          console.error('Export failed:', err);
        });
      } else if (format === 'svg') {
        // Use type assertion since svg() method may not be in type definitions
        const cy = cyRef.current as any;
        if (cy.svg) {
          const svgString = cy.svg({ full: true });
          const blob = new Blob([svgString], { type: 'image/svg+xml' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = 'grn-network.svg';
          link.click();
          URL.revokeObjectURL(url);
        } else {
          console.warn('SVG export not available, falling back to PNG');
          handleExport('png');
        }
      }
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  return (
    <div className="grn-visualization-container">
      <div className="grn-controls">
        <div className="control-group">
          <label>显示模式:</label>
          <select 
            value={displayMode}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setDisplayMode(e.target.value as any)}
          >
            <option value="all">全部显示</option>
            <option value="top_edges">仅高权重边</option>
            <option value="top_nodes">仅重要节点</option>
          </select>
        </div>
        {(displayMode === 'top_edges' || displayMode === 'top_nodes') && (
          <div className="control-group">
            <label>最大数量:</label>
            <input
              type="number"
              min={10}
              max={200}
              value={maxElements}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMaxElements(parseInt(e.target.value) || 50)}
              style={{ width: '80px', padding: '4px' }}
            />
          </div>
        )}
        <div className="control-group">
          <label>权重阈值: {weightThreshold.toFixed(4)}</label>
          <input
            type="range"
            min={minWeight}
            max={maxWeight}
            step={(maxWeight - minWeight) / 100}
            value={weightThreshold}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWeightThreshold(parseFloat(e.target.value))}
          />
          <span className="weight-range">
            {minWeight.toFixed(4)} - {maxWeight.toFixed(4)}
          </span>
        </div>
        <div className="control-group">
          <label>布局:</label>
          <select onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleLayoutChange(e.target.value)}>
            <option value="breadthfirst">层次布局</option>
            <option value="grid">网格布局</option>
            <option value="circle">圆形布局</option>
            <option value="concentric">同心圆布局</option>
            <option value="random">随机布局</option>
          </select>
        </div>
        <div className="control-group">
          <button onClick={handleResetView}>重置视图</button>
          <button onClick={() => handleExport('png')}>导出 PNG</button>
          <button onClick={() => handleExport('svg')}>导出 SVG</button>
        </div>
        <div className="stats">
          <span>
            显示节点: {(() => {
              const filtered = getFilteredEdges();
              const nodeSet = new Set<string>();
              filtered.forEach((e: GRNEdge) => {
                nodeSet.add(e.source);
                nodeSet.add(e.target);
              });
              return nodeSet.size;
            })()}
          </span>
          <span>
            显示边数: {getFilteredEdges().length}
          </span>
          <span>
            总边数: {edges.length}
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="grn-cytoscape-container"
        style={{ height: `${height}px` }}
      />
    </div>
  );
};

export default GRNVisualization;

