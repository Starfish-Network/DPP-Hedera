import { useEffect } from "react";
import { useEventFiles } from "../hooks/useEventFiles";
import type { GDSTEvent } from "../types/GDSTEvent";
import type { StarfishEvent } from "../types/StarfishEvents";

type EventFilesProps = {
    evt: ((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string });
    refetchTrigger?: number;
    gdstEvent?: boolean;
};

export function EventFiles({ evt, refetchTrigger, gdstEvent }: EventFilesProps) {
    const { files, refetch } = useEventFiles(evt.event_hash, gdstEvent);

    useEffect(() => {
        if (refetchTrigger !== undefined) {
            refetch();
        }
    }, [refetchTrigger, refetch]);

    return (
        files && files.length > 0 && (
            <div className="mt-2">
                <div className="font-semibold text-xs mb-1">Attached Files:</div>
                <ul>
                    {files.map((cid) => (
                        <li key={cid}>
                            <a
                                href={`/api/v1/${gdstEvent ? "gdst" : "epcis"}/events/${evt.event_hash}/files/${cid}/download`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 underline text-xs"
                            >
                                {cid}
                            </a>
                        </li>
                    ))}
                </ul>
            </div>
        )
    )
}