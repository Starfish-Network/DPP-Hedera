import { useEffect } from "react";
import { useEventFiles } from "../hooks/useEventFiles";
import type { StarfishEvent } from "../types/StarfishEvents";

type EventFilesProps = {
    evt: StarfishEvent & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string };
    refetchTrigger?: number;
};

export function EventFiles({ evt, refetchTrigger }: EventFilesProps) {
    const { files, refetch } = useEventFiles(evt.event_hash);

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
                                href={`/api/v1/events/${evt.event_hash}/files/${cid}/download`}
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