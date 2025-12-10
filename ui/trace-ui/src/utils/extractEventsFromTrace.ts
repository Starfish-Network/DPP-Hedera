import type { StarfishEvent } from "../types/StarfishEvents";
import type { TraceResponse } from "../types/TraceResponse";

export function extractEventsFromTrace(
    epc: string,
    traceResponse: TraceResponse
): (StarfishEvent & { consensus_timestamp: string; event_hash: string; isCompliant: boolean | null })[] {
    const getEvents = (edge?: { event_starfish_ids?: (StarfishEvent & { event_hash?: string; consensus_timestamp?: string })[] }) =>
        edge?.event_starfish_ids?.map(evt => ({
            ...evt,
            isCompliant: null,
            event_hash: evt.event_hash ?? "",
            consensus_timestamp: evt.consensus_timestamp ?? ""
        })) ?? [];

    const allEvents = [
        ...getEvents(traceResponse.upstream_result.edge_list_dict[epc]),
        ...getEvents(traceResponse.downstream_result.edge_list_dict[epc]),
    ];

    // Deduplicate by event_hash
    const uniqueEvents = Array.from(
        new Map(allEvents.map(evt => [evt.event_hash, evt])).values()
    );

    return uniqueEvents;
}