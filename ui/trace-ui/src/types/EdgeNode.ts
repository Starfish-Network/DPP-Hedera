import type { StarfishEvent } from "./StarfishEvents";

export interface EdgeNode {
    identifier: string;
    event_starfish_ids?: (StarfishEvent & { consensus_timestamp: string; event_hash: string })[];
    related_nodes: [string, string][];
}