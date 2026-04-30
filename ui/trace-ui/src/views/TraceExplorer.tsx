import { useCallback, useEffect, useState } from "react";
import type { Edge, Node } from "reactflow";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState
} from "reactflow";
import "reactflow/dist/style.css";
import { GraphLegend } from "../components/GraphLegend";
import { NodeModal } from "../components/NodeModal";
import type { EdgeNode } from "../types/EdgeNode";
import type { GDSTEvent } from "../types/GDSTEvent";
import type { StarfishEvent } from "../types/StarfishEvents";
import type { TraceResponse } from "../types/TraceResponse";
import { extractEventsFromTrace } from "../utils/extractEventsFromTrace";
import { getLayoutedElements } from "../utils/getLayoutedElements";

const nodeStyles = {
  upstream: {
    background: "#dbeafe", // blue-100
    border: "1px solid #3b82f6", // blue-500
  },
  downstream: {
    background: "#dcfce7", // green-100
    border: "1px solid #16a34a", // green-600
  },
  current: {
    background: "#f8fafc", // gray-50
    border: "2px solid #64748b", // slate-500
  },
};

export function TraceExplorer() {
  const [productId, setProductId] = useState("");
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [eventsForNode, setEventsForNode] = useState<((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string })[]>([]);
  const [allEvents, setAllEvents] = useState<((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string })[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);

  const onNodeClick = useCallback(async (_: unknown, node: Node) => {
    if (!trace) return;
    setIsLoadingEvents(true);
    const events = extractEventsFromTrace(node.id, trace);
    setAllEvents(events);
    setSelectedNode(node);
    await fetchComplianceForEvents(events.slice(0, 1));
    setIsLoadingEvents(false);
  }, [trace]);

  const fetchComplianceForEvents = async (events: ((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string })[]) => {
    const updatedEvents = await Promise.all(
      events.map(async (evt) => {
        const isGDST = "gdst_event_type" in evt;
        try {
          const res = await fetch(`/api/v1/${isGDST ? "gdst" : "epcis"}/compliance/status/${evt.event_hash}`, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
          });
          const data = await res.json() as { isCompliant: boolean | null };
          return { ...evt, isCompliant: data.isCompliant };
        } catch {
          return { ...evt, isCompliant: null };
        }
      })
    );
    setEventsForNode(updatedEvents);
  }

  const fetchTrace = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/trace/${productId}`);
      const data = await res.json();
      setTrace(data);
    } catch (err) {
      console.error("Failed to fetch trace:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!trace) return;

    const upstream = trace.upstream_result?.edge_list_dict;
    const downstream = trace.downstream_result?.edge_list_dict;

    const buildNodes = (
      data: Record<string, EdgeNode>,
      type: "upstream" | "downstream"
    ): Node[] =>
      Object.values(data).map((node: EdgeNode) => ({
        id: node.identifier,
        data: {
          label: (
            <div className="text-sm font-semibold text-center">
              {node.identifier}
              <div className="text-xs text-gray-500">
                {node.event_starfish_ids?.length ?? 0} txs
              </div>
            </div>
          ),
        },
        style: {
          ...nodeStyles[type],
          width: 200,
          height: 70,
          borderRadius: "8px",
          padding: "8px",
        },
        position: { x: 0, y: 0 },
      }));

    const upNodes = buildNodes(upstream, "upstream");
    const downNodes = buildNodes(downstream, "downstream");

    const current =
      productId.length > 0
        ? [
          {
            id: productId,
            data: { label: <div className="font-bold">{productId}</div> },
            style: { ...nodeStyles.current, width: 200, height: 70 },
            position: { x: 0, y: 0 },
          },
        ]
        : [];

    const buildEdges = (data: Record<string, EdgeNode>): Edge[] =>
      Object.values(data).flatMap((node: EdgeNode) =>
        node.related_nodes.map(([relId, relType]: [string, string]) => ({
          id: `${node.identifier}-${relId}`,
          source: relType === "parent" ? relId : node.identifier,
          target: relType === "parent" ? node.identifier : relId,
          type: "smoothstep",
        }))
      );

    const combinedEdges = [
      ...buildEdges(upstream),
      ...buildEdges(downstream),
    ];

    const layouted = getLayoutedElements(
      [...upNodes, ...downNodes, ...current],
      combinedEdges
    );

    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [trace, productId, setNodes, setEdges]);

  const fetchAllEvents = useCallback(async () => {
    if (!selectedNode || !trace) return;
    await fetchComplianceForEvents(allEvents);
  }, [selectedNode, trace, allEvents]);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">🧭 Trace Explorer</h2>

      <div className="flex gap-2 mb-6">
        <input
          className="border border-gray-300 rounded-md px-4 py-2 flex-1"
          placeholder="Enter Product EPC / Lot"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
        />
        <button
          onClick={fetchTrace}
          disabled={!productId || loading}
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
        >
          {loading ? "Tracing..." : "Trace"}
        </button>
      </div>

      {trace ? (
        <div className="h-[600px] border rounded-lg shadow bg-white relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
          >
            <MiniMap nodeColor={(n) => String(n.style?.background ?? "#ccc")} />
            <Controls />
            <Background color="#f3f4f6" gap={16} />
          </ReactFlow>

          {selectedNode && (
            <NodeModal
              eventList={eventsForNode}
              setShowAll={fetchAllEvents}
              totalEvents={allEvents.length}
              onClose={() => setSelectedNode(null)}
              isLoadingEvents={isLoadingEvents}
            />
          )}
          <GraphLegend />
        </div>
      ) : (
        <p className="text-gray-600 italic">Enter a product EPC to begin tracing.</p>
      )}
    </div>
  );
}
