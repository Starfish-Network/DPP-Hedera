import type { EdgeNode } from "./EdgeNode";

export interface TraceResponse {
    upstream_result: { edge_list_dict: Record<string, EdgeNode> };
    downstream_result: { edge_list_dict: Record<string, EdgeNode> };
}