'use client';

import { useJarvisStatus } from '@/hooks/useJarvisStatus';

interface AgentNode {
  variant: string;
  status: string;
  current: number;
  max: number;
  x: number;
  y: number;
}

function buildNodes(loadStatus: any[]): { nodes: AgentNode[]; connections: [number, number][] } {
  if (!loadStatus || loadStatus.length === 0) return { nodes: [], connections: [] };

  const nodes: AgentNode[] = loadStatus.map((agent, idx) => {
    const cols = Math.ceil(Math.sqrt(loadStatus.length));
    const row = Math.floor(idx / cols);
    const col = idx % cols;
    return {
      variant: agent.variant || `Agent-${idx + 1}`,
      status: agent.status || 'idle',
      current: agent.current_concurrent || 0,
      max: agent.max_concurrent || 10,
      x: 50 + col * 100,
      y: 50 + row * 80,
    };
  });

  const connections: [number, number][] = [];
  for (let i = 0; i < nodes.length - 1; i++) {
    connections.push([i, i + 1]);
  }

  return { nodes, connections };
}

function nodeColor(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'running':
      return '#00ff88';
    case 'idle':
    case 'standby':
      return '#06b6d4';
    case 'busy':
      return '#f59e0b';
    case 'error':
    case 'down':
      return '#ef4444';
    default:
      return '#6b7280';
  }
}

export default function WorkforceMap() {
  const { data: status, isLoading } = useJarvisStatus();
  const agents = status?.load_status || [];
  const { nodes, connections } = buildNodes(agents);

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Workforce Allocation</h3>
        <div className="skeleton h-48 rounded" />
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Workforce Allocation</h3>
        <div className="text-center py-10 text-jarvis-muted text-sm">
          No agent allocation data
        </div>
      </div>
    );
  }

  const svgW = Math.max(200, nodes.length * 100 + 60);
  const svgH = Math.max(120, Math.ceil(nodes.length / Math.ceil(Math.sqrt(nodes.length))) * 80 + 60);

  return (
    <div className="jarvis-card">
      <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Workforce Allocation</h3>
      <div className="bg-jarvis-bg/50 rounded-lg border border-jarvis-border/30 p-2 overflow-x-auto">
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full h-48 min-w-[200px]"
          style={{ minWidth: svgW }}
        >
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Grid lines */}
          <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#1f2937" strokeWidth="0.5" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Connections */}
          {connections.map(([from, to], idx) => (
            <line
              key={idx}
              x1={nodes[from].x}
              y1={nodes[from].y}
              x2={nodes[to].x}
              y2={nodes[to].y}
              stroke="#1f2937"
              strokeWidth="1"
              strokeDasharray="4,4"
            />
          ))}

          {/* Center node */}
          <circle cx={svgW / 2} cy={svgH / 2} r="16" fill="none" stroke="#00ff88" strokeWidth="1" opacity="0.3" />
          <text x={svgW / 2} y={svgH / 2 + 4} textAnchor="middle" fill="#00ff88" fontSize="8" fontFamily="monospace">JARVIS</text>

          {/* Agent nodes */}
          {nodes.map((node, idx) => {
            const color = nodeColor(node.status);
            const load = node.max > 0 ? Math.round((node.current / node.max) * 100) : 0;
            return (
              <g key={idx} filter="url(#glow)">
                <circle
                  cx={node.x}
                  cy={node.y}
                  r="22"
                  fill={`${color}10`}
                  stroke={color}
                  strokeWidth="1.5"
                />
                <text
                  x={node.x}
                  y={node.y - 4}
                  textAnchor="middle"
                  fill={color}
                  fontSize="7"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  {node.variant.length > 10 ? node.variant.slice(0, 9) + '…' : node.variant}
                </text>
                <text
                  x={node.x}
                  y={node.y + 7}
                  textAnchor="middle"
                  fill="#9ca3af"
                  fontSize="6"
                  fontFamily="monospace"
                >
                  {load}% load
                </text>
                <text
                  x={node.x}
                  y={node.y + 16}
                  textAnchor="middle"
                  fill="#6b7280"
                  fontSize="5"
                  fontFamily="monospace"
                >
                  {node.current}/{node.max}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}