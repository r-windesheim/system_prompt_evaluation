import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Card } from './Card';

interface Node {
  id: string;
  label: string;
  description: string;
  full_text?: string;
  type: 'section' | 'quirk';
  group: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface Edge {
  source: string;
  target: string;
  weight: number;
  spike_ratio: number;
  impact: number;
  with_section: number;
  without_section: number;
  p_value: number;
  effect_size: number;
  significant: boolean;
}

interface NetworkGraphProps {
  nodes: Node[];
  edges: Edge[];
}

// Color mapping - vibrant, modern palette
const SECTION_COLORS = [
  '#6366f1', // Indigo
  '#8b5cf6', // Purple
  '#ec4899', // Pink
  '#f59e0b', // Amber
  '#10b981', // Emerald
  '#06b6d4', // Cyan
  '#3b82f6', // Blue
  '#ef4444', // Red
];

const getNodeColor = (node: Node) => {
  if (node.type === 'section') {
    const idx = parseInt(node.id.replace('section_', '')) || 0;
    return SECTION_COLORS[idx % SECTION_COLORS.length];
  }
  return '#64748b'; // Slate gray for quirks
};

const getNodeSize = (node: Node, connectedEdges: Edge[]) => {
  if (node.type === 'section') {
    return 12 + Math.min(connectedEdges.length * 2, 8);
  }
  return 8 + Math.min(connectedEdges.length * 1.5, 6);
};

const getEdgeWidth = (edge: Edge, allEdges: Edge[]) => {
  const minWidth = 1.5;
  const maxWidth = 6;
  const maxImpact = Math.max(...allEdges.map(e => Math.abs(e.impact)), 1);
  return minWidth + (Math.abs(edge.impact) / maxImpact) * (maxWidth - minWidth);
};

const getEdgeColor = (edge: Edge) => {
  if (edge.impact > 0) return '#10b981'; // Green for increases
  return '#ef4444'; // Red for decreases
};

const getEdgeOpacity = (edge: Edge) => {
  const baseOpacity = 0.5;
  const maxOpacity = 0.9;
  return Math.min(baseOpacity + (edge.spike_ratio - 1) * 0.1, maxOpacity);
};

export const NetworkGraph: React.FC<NetworkGraphProps> = ({ nodes, edges }) => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 1000, height: 700 });
  const [isMounted, setIsMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);

  // Ensure component only renders on client
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Prepare graph data
  const graphData = useMemo(() => {
    // Calculate connections for each node
    const nodeConnections = new Map<string, Edge[]>();
    edges.forEach(edge => {
      if (!nodeConnections.has(edge.source)) {
        nodeConnections.set(edge.source, []);
      }
      if (!nodeConnections.has(edge.target)) {
        nodeConnections.set(edge.target, []);
      }
      nodeConnections.get(edge.source)!.push(edge);
      nodeConnections.get(edge.target)!.push(edge);
    });

    return {
      nodes: nodes.map(node => ({
        ...node,
        color: getNodeColor(node),
        size: getNodeSize(node, nodeConnections.get(node.id) || []),
        connections: nodeConnections.get(node.id)?.length || 0,
      })),
      links: edges.map(edge => ({
        ...edge,
        source: edge.source,
        target: edge.target,
        color: getEdgeColor(edge),
        width: getEdgeWidth(edge, edges),
        opacity: getEdgeOpacity(edge),
      })),
    };
  }, [nodes, edges]);

  // Update dimensions
  React.useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const width = Math.max(800, containerRef.current.offsetWidth - 40);
        const height = Math.max(600, width * 0.7);
        setDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Get edges connected to a node
  const getConnectedEdges = useCallback((nodeId: string) => {
    return edges.filter(e => e.source === nodeId || e.target === nodeId);
  }, [edges]);

  // Get node by id
  const getNode = useCallback((id: string) => {
    return nodes.find(n => n.id === id);
  }, [nodes]);

  // Handle node hover
  const handleNodeHover = useCallback((node: any) => {
    setHoveredNode(node?.id || null);
  }, []);

  // Handle node click
  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(prev => prev === node?.id ? null : node?.id || null);
  }, []);

  // Reset view
  const resetView = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 20);
    }
  }, []);

  // Don't render until mounted (client-side only)
  if (!isMounted) {
    return (
      <Card padding="lg">
        <div className="text-center text-text-secondary py-8">
          Loading network graph...
        </div>
      </Card>
    );
  }

  if (!nodes.length) {
    return (
      <Card padding="lg">
        <div className="text-center text-text-secondary py-8">
          No network data available
        </div>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
        <div>
            <div className="flex items-center space-x-3 mb-2">
              <svg className="w-7 h-7 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-primary via-purple-500 to-accent bg-clip-text text-transparent">
              Section → Quirk Network
            </h2>
          </div>
            <p className="text-sm text-text-secondary ml-10">
              Interactive network showing which prompt sections cause which behavioral quirks
            </p>
          </div>
          <button
            onClick={resetView}
            className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary bg-surface hover:bg-surface-elevated border border-border rounded-lg transition-colors shadow-sm"
            title="Reset zoom and pan"
          >
            Reset View
          </button>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-xs bg-gradient-to-r from-surface-elevated to-surface border border-border rounded-lg p-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md"></div>
            <span className="text-text-secondary font-medium">Prompt Sections</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-slate-500 shadow-md"></div>
            <span className="text-text-secondary font-medium">Detected Quirks</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-10 h-1.5 bg-gradient-to-r from-green-500 to-emerald-400 rounded-full shadow-sm"></div>
            <span className="text-text-secondary">Increases behavior</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-10 h-1.5 bg-gradient-to-r from-red-500 to-rose-400 rounded-full shadow-sm"></div>
            <span className="text-text-secondary">Decreases behavior</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-2 bg-primary rounded-full shadow-sm"></div>
            <span className="text-text-secondary">Thicker = Stronger impact</span>
          </div>
        </div>

        {/* Graph Container */}
        <div 
          ref={containerRef} 
          className="bg-gradient-to-br from-slate-50 via-white to-slate-50 border-2 border-border rounded-xl overflow-hidden shadow-xl relative"
          style={{ minHeight: '600px' }}
        >
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            nodeLabel={(node: any) => `
              <div style="
                background: rgba(15, 23, 42, 0.95);
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                border: 1px solid rgba(148, 163, 184, 0.3);
              ">
                <div style="font-size: 14px; margin-bottom: 4px;">${node.label}</div>
                <div style="font-size: 10px; color: #94a3b8; font-weight: 400;">
                  ${node.type === 'section' ? 'Prompt Section' : 'Behavioral Quirk'}
                </div>
                ${node.connections > 0 ? `<div style="font-size: 10px; color: #64748b; margin-top: 4px;">${node.connections} connections</div>` : ''}
              </div>
            `}
            nodeColor={(node: any) => node.color}
            nodeVal={(node: any) => node.size}
            nodeRelSize={6}
            linkColor={(link: any) => link.color}
            linkWidth={(link: any) => link.width}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            linkDirectionalArrowColor={(link: any) => link.color}
            linkCurvature={0.25}
            onNodeHover={handleNodeHover}
            onNodeClick={handleNodeClick}
            cooldownTicks={100}
            onEngineStop={() => {
              if (graphRef.current) {
                graphRef.current.zoomToFit(400, 20);
              }
            }}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              // Validate node position and size are finite numbers
              if (!node.x || !node.y || !isFinite(node.x) || !isFinite(node.y) || !isFinite(node.size)) {
                return; // Skip rendering if values are invalid
              }

              const label = node.label;
              const fontSize = 12 / globalScale;
              ctx.font = `${fontSize}px Inter, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              
              // Draw node with glow effect
              const isHighlighted = hoveredNode === node.id || selectedNode === node.id;
              const radius = Math.max(1, node.size || 8); // Ensure radius is at least 1
              
              // Outer glow for highlighted nodes
              if (isHighlighted) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
                ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
                ctx.fill();
              }
              
              // Main node circle with gradient effect
              const gradientX = node.x - radius * 0.3;
              const gradientY = node.y - radius * 0.3;
              
              // Validate gradient coordinates are finite
              if (isFinite(gradientX) && isFinite(gradientY) && isFinite(radius)) {
                const gradient = ctx.createRadialGradient(
                  gradientX, gradientY, 0,
                  node.x, node.y, radius
                );
                gradient.addColorStop(0, node.color);
                gradient.addColorStop(1, node.color + 'dd');
                
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                ctx.fillStyle = gradient;
                ctx.fill();
              } else {
                // Fallback to solid color if gradient fails
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                ctx.fillStyle = node.color;
                ctx.fill();
              }
              
              // Border
              ctx.strokeStyle = isHighlighted ? '#fff' : 'rgba(255, 255, 255, 0.3)';
              ctx.lineWidth = isHighlighted ? 3 / globalScale : 1.5 / globalScale;
              ctx.stroke();
              
              // Inner highlight
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius * 0.6, 0, 2 * Math.PI);
              ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
              ctx.fill();
              
              // Label background
              const textWidth = ctx.measureText(label).width;
              const labelPadding = 6 / globalScale;
              const labelHeight = fontSize + labelPadding * 2;
              const labelY = node.y + radius + labelHeight / 2 + 4 / globalScale;
              
              ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
              const rectX = node.x - textWidth / 2 - labelPadding;
              const rectY = labelY - labelHeight / 2;
              const rectW = textWidth + labelPadding * 2;
              const rectH = labelHeight;
              const cornerRadius = 4 / globalScale;
              
              ctx.beginPath();
              ctx.moveTo(rectX + cornerRadius, rectY);
              ctx.lineTo(rectX + rectW - cornerRadius, rectY);
              ctx.quadraticCurveTo(rectX + rectW, rectY, rectX + rectW, rectY + cornerRadius);
              ctx.lineTo(rectX + rectW, rectY + rectH - cornerRadius);
              ctx.quadraticCurveTo(rectX + rectW, rectY + rectH, rectX + rectW - cornerRadius, rectY + rectH);
              ctx.lineTo(rectX + cornerRadius, rectY + rectH);
              ctx.quadraticCurveTo(rectX, rectY + rectH, rectX, rectY + rectH - cornerRadius);
              ctx.lineTo(rectX, rectY + cornerRadius);
              ctx.quadraticCurveTo(rectX, rectY, rectX + cornerRadius, rectY);
              ctx.closePath();
              ctx.fill();
              ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)';
              ctx.lineWidth = 1 / globalScale;
              ctx.stroke();
              
              // Label text
              ctx.fillStyle = '#e2e8f0';
              ctx.fillText(label, node.x, labelY);
              
              // Connection count badge
              if (node.connections > 0) {
                const badgeRadius = 8 / globalScale;
                const badgeX = node.x + radius - badgeRadius;
                const badgeY = node.y - radius + badgeRadius;
                
                ctx.beginPath();
                ctx.arc(badgeX, badgeY, badgeRadius, 0, 2 * Math.PI);
                ctx.fillStyle = node.color;
                ctx.fill();
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
                
              ctx.fillStyle = '#fff';
              ctx.font = `bold ${10 / globalScale}px Inter, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillText(node.connections.toString(), badgeX, badgeY);
              }
            }}
            linkCanvasObject={(link: any, ctx: CanvasRenderingContext2D) => {
              // Validate link coordinates are finite
              if (!link.source || !link.target || 
                  !isFinite(link.source.x) || !isFinite(link.source.y) ||
                  !isFinite(link.target.x) || !isFinite(link.target.y)) {
                return; // Skip rendering if values are invalid
              }

              const isHighlighted = 
                hoveredNode === link.source.id || 
                hoveredNode === link.target.id ||
                selectedNode === link.source.id ||
                selectedNode === link.target.id;
              
              // Apply opacity to all links
              ctx.save();
              ctx.globalAlpha = isHighlighted ? 0.95 : link.opacity || 0.5;
              
              if (isHighlighted) {
                // Draw highlighted link with glow
                ctx.strokeStyle = link.color;
                ctx.lineWidth = link.width + 4;
                ctx.beginPath();
                ctx.moveTo(link.source.x, link.source.y);
                ctx.lineTo(link.target.x, link.target.y);
                ctx.stroke();
              }
              
              ctx.restore();
            }}
          />
        </div>

        {/* Node Details Panel */}
        {selectedNode && (
          <div className="bg-gradient-to-br from-surface-elevated to-surface border-2 border-primary/50 rounded-xl p-6 shadow-xl animate-in">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-4">
                <div
                  className="w-14 h-14 rounded-full shadow-lg flex items-center justify-center ring-4 ring-white/20"
                  style={{ 
                    backgroundColor: getNodeColor(getNode(selectedNode)!),
                    boxShadow: `0 8px 24px ${getNodeColor(getNode(selectedNode)!) || '#000'}50`
                  }}
                >
                  <span className="text-white font-bold text-xl">
                    {getNode(selectedNode)?.type === 'section' 
                      ? getNode(selectedNode)?.label.replace('Section ', '')
                      : getNode(selectedNode)?.label.charAt(0)}
                  </span>
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-text-primary mb-1">
                    {getNode(selectedNode)?.label}
                  </h3>
                  <p className="text-sm text-text-secondary mb-2">
                    {getNode(selectedNode)?.description}
                  </p>
                  <div>
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                      getNode(selectedNode)?.type === 'section'
                        ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                        : 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
                    }`}>
                      {getNode(selectedNode)?.type === 'section' ? 'Prompt Section' : 'Behavioral Quirk'}
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-text-secondary hover:text-text-primary transition-colors p-2 hover:bg-surface rounded-lg"
                title="Close details"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Show full text for sections */}
            {getNode(selectedNode)?.type === 'section' && getNode(selectedNode)?.full_text && (
              <div className="mb-5 p-4 bg-surface rounded-lg border border-border/50">
                <div className="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wide">Section Content:</div>
                <div className="text-sm text-text-primary leading-relaxed italic">
                  "{getNode(selectedNode)?.full_text}"
                </div>
              </div>
            )}

            {/* Connected edges */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="text-lg font-bold text-text-primary">
                  Connections
                </div>
                <div className="px-3 py-1 bg-primary/20 text-primary rounded-full text-sm font-bold">
                  {getConnectedEdges(selectedNode).length}
                </div>
              </div>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                {getConnectedEdges(selectedNode).map((edge, idx) => {
                  const otherNodeId = edge.source === selectedNode ? edge.target : edge.source;
                  const otherNode = getNode(otherNodeId);
                  const isIncrease = edge.impact > 0;

                  return (
                    <div
                      key={idx}
                      className="p-4 bg-surface rounded-lg border-2 border-border hover:border-primary/50 transition-all cursor-pointer hover:shadow-lg group"
                      onClick={() => setSelectedNode(otherNodeId)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-3">
                            <div
                              className="w-4 h-4 rounded-full flex-shrink-0 shadow-sm"
                              style={{ backgroundColor: getNodeColor(otherNode!) }}
                            ></div>
                            <div className="text-base font-bold text-text-primary truncate">
                            {otherNode?.label}
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-4 text-sm text-text-secondary">
                            <span className="flex items-center gap-2">
                              <span className="font-semibold">Impact:</span>
                              <span className={`font-bold text-base ${isIncrease ? 'text-green-500' : 'text-red-500'}`}>
                                {isIncrease ? '+' : ''}{edge.impact.toFixed(2)}
                              </span>
                            </span>
                            <span className="flex items-center gap-2">
                              <span className="font-semibold">Spike:</span>
                              <span className="font-bold text-base text-text-primary">{edge.spike_ratio.toFixed(2)}x</span>
                            </span>
                            {edge.significant && (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-500/20 text-green-500 rounded-full font-semibold border border-green-500/30">
                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                </svg>
                                Significant
                              </span>
                            )}
                          </div>
                        </div>
                        <div
                          className={`px-4 py-2 rounded-lg text-sm font-bold flex-shrink-0 shadow-md ${
                            isIncrease
                              ? 'bg-green-500/20 text-green-500 border-2 border-green-500/40'
                              : 'bg-red-500/20 text-red-500 border-2 border-red-500/40'
                          }`}
                        >
                          {isIncrease ? '↑ Increase' : '↓ Decrease'}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Info */}
        <div className="text-sm text-text-secondary bg-gradient-to-r from-surface-elevated to-surface border border-border rounded-lg p-4">
          <div className="flex items-start gap-3">
            <span className="text-lg">💡</span>
            <div>
              <strong className="text-text-primary">Tip:</strong> Click on any node to see detailed connections and impact metrics.
              Drag nodes to rearrange, scroll to zoom. Thicker lines indicate stronger impacts. Green = behavior increases, Red = behavior decreases.
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};
