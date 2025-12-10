import { useCallback, useEffect, useState } from "react";

export function useEventFiles(event_hash: string) {
    const [files, setFiles] = useState<string[]>([]);

    const fetchFiles = useCallback(async () => {
        try {
            const res = await fetch(`/api/v1/events/${event_hash}/files`);
            if (!res.ok) return [];
            const data = await res.json();
            return data.fileCids || [];
        } catch {
            return [];
        }
    }, [event_hash]);

    // Fetch files on mount and when event_hash changes
    useEffect(() => {
        fetchFiles().then(setFiles);
    }, [fetchFiles]);

    // Refetch function for manual refresh
    const refetch = useCallback(async () => {
        const newFiles = await fetchFiles();
        setFiles(newFiles);
    }, [fetchFiles]);

    return { files, refetch };
}