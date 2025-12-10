from collections import deque

def build_edge_list(graph, nodes):
    edge_list = {}
    for epc, depth in nodes.items():
        node = {
            "trace_id": epc,
            "identifier": epc,
            "related_nodes": [],
            "event_starfish_ids": list(graph[epc]["events"]),
            "org_starfish_id": "org-placeholder",
            "depth": depth,
        }
        # Add input/output relationships
        for parent in graph[epc]["inputs"]:
            node["related_nodes"].append([parent, "parent"])
        for child in graph[epc]["outputs"]:
            node["related_nodes"].append([child, "child"])
        edge_list[epc] = node
    return edge_list

# BFS traversals for upstream and downstream lineage
def traverse(graph, start_epc, direction="upstream"):
    start_epc = normalize_epc(start_epc)
    visited = {}
    queue = deque([(start_epc, 0)])
    while queue:
        epc, depth = queue.popleft()
        if epc in visited:
            continue
        visited[epc] = depth
        next_nodes = (
            graph[epc]["inputs"] if direction == "upstream" else graph[epc]["outputs"]
        )
        for n in next_nodes:
            if n not in visited:
                queue.append((n, depth + 1))
    return visited

def normalize_epc(epc: str) -> str:
    if not epc:
        return ""
    return epc.strip()
