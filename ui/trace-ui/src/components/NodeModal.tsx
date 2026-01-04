import { useEffect, useRef, useState } from "react";
import type { ComplianceCheckResponse } from "../types/ComplianceCheckResponse";
import type { GDSTEvent } from "../types/GDSTEvent";
import type { StarfishEvent } from "../types/StarfishEvents";
import { EventFiles } from "./EventFiles";

type NodeModalProps = {
    readonly eventList: ((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string })[];
    readonly onClose: () => void;
    readonly totalEvents: number;
    readonly setShowAll: (showAll: boolean) => void;
    readonly isLoadingEvents?: boolean;
};

export function NodeModal({ eventList, onClose, totalEvents, setShowAll, isLoadingEvents }: NodeModalProps) {
    const [compliance, setCompliance] = useState<Record<string, ComplianceCheckResponse>>({});
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [refreshKeys, setRefreshKeys] = useState<Record<string, number>>({});

    // Handler to trigger file input
    const handleAttachClick = () => {
        fileInputRef.current?.click();
    };

    // Handler for file selection and upload
    const handleFileChange = async (evt: React.ChangeEvent<HTMLInputElement>, event_hash: string) => {
        const file = evt.target.files?.[0];
        if (!file) return;
        setUploading(true);
        setUploadResult(null);
        try {
            const formData = new FormData();
            formData.append("file", file);
            const res = await fetch(`/api/v1/events/${event_hash}/attach`, {
                method: "POST",
                body: formData,
            });
            if (!res.ok) throw new Error("Upload failed");
            const data = await res.json();
            setUploadResult(`File uploaded! CID: ${data.fileCid}`);
            // Increment refreshKey for this event_hash
            setRefreshKeys(prev => ({
                ...prev,
                [event_hash]: (prev[event_hash] || 0) + 1
            }));
        } catch {
            setUploadResult("Upload failed.");
        } finally {
            setUploading(false);
        }
    };

    useEffect(() => {
        const initialCompliance: Record<string, ComplianceCheckResponse> = {};
        for (const evt of eventList) {
            if (evt.isCompliant !== null) {
                initialCompliance[evt.consensus_timestamp] = {
                    isCompliant: evt.isCompliant,
                    eventHashHex: evt.event_hash,
                };
            }
        }
        setCompliance(initialCompliance);
    }, [eventList]);

    async function runComplianceCheck(evt: ((StarfishEvent | GDSTEvent) & { consensus_timestamp: string; isCompliant: boolean | null; event_hash: string })) {
        setLoading(true);
        try {
            const res = await fetch(`/api/v1/compliance/check`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(evt),
            });
            const data = await res.json() as ComplianceCheckResponse;

            setCompliance((prev) => ({
                ...prev,
                [evt.consensus_timestamp]: data,
            }));
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
                className="relative p-6 bg-white rounded-xl shadow-xl max-w-3xl mx-auto"
                style={{
                    maxHeight: "80vh",
                    overflowY: "auto",
                }}
            >
                {/* "X" Close Button at top right */}
                <button
                    type="button"
                    className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 text-2xl font-bold focus:outline-none"
                    onClick={onClose}
                    tabIndex={0}
                    aria-label="Close Modal"
                    onKeyDown={e => {
                        if (e.key === "Enter" || e.key === " ") {
                            onClose();
                        }
                    }}
                >
                    &times;
                </button>

                <h2 className="text-xl font-bold mb-4">Event Details</h2>

                {isLoadingEvents ? (
                    <div className="p-4 text-center text-gray-600">Loading events...</div>
                ) : (
                    eventList.map((evt) => {
                        const json = JSON.stringify(evt, null, 2);
                        const c = compliance[evt.consensus_timestamp];

                        return (
                            <div key={evt.consensus_timestamp} className="border rounded p-4 mb-4 bg-gray-50">
                                <pre className="text-xs">{json}</pre>
                                {c ? (
                                    <div className={`mt-2 p-2 border rounded ${c.isCompliant ? "bg-green-100 border-green-400" : "bg-red-100 border-red-400"}`}>
                                        {c.isCompliant
                                            ? <>✅ Compliant</>
                                            : <>Not compliant</>
                                        }
                                        <button
                                            type="button"
                                            disabled={loading}
                                            onClick={() => runComplianceCheck(evt)}
                                            className="ml-4 px-2 py-1 bg-blue-200 border border-blue-400 rounded text-blue-700 text-xs cursor-pointer hover:bg-blue-300 disabled:opacity-50 disabled:cursor-not-allowed"
                                            tabIndex={0}
                                            aria-label="Run again"
                                        >
                                            Run again
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        type="button"
                                        disabled={loading}
                                        onClick={() => runComplianceCheck(evt)}
                                        className="mt-2 px-3 py-1 bg-blue-600 text-white rounded text-sm cursor-pointer hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                        tabIndex={0}
                                        aria-label="Run Compliance Check"
                                        onKeyDown={e => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                runComplianceCheck(evt);
                                            }
                                        }}
                                    >
                                        {loading ? "Running Compliance Check..." : "Run Compliance Check"}
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={handleAttachClick}
                                    disabled={uploading}
                                    className="mt-2 px-3 py-1 bg-purple-600 text-white rounded text-sm"
                                >
                                    {uploading ? "Uploading..." : "Attach File"}
                                </button>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    style={{ display: "none" }}
                                    onChange={e => handleFileChange(e, evt.event_hash)}
                                />
                                {uploadResult && <div className="mt-2 text-xs">{uploadResult}</div>}
                                <EventFiles
                                    evt={evt}
                                    refetchTrigger={refreshKeys[evt.event_hash]}
                                    gdstEvent={"gdst_event_type" in evt}
                                />
                            </div>
                        );
                    })
                )}

                {totalEvents > 1 && eventList.length < totalEvents && (
                    <button
                        type="button"
                        onClick={() => setShowAll(true)}
                        className="mb-2 px-4 py-2 bg-blue-100 border border-blue-400 rounded text-blue-700 cursor-pointer hover:bg-blue-200"
                        tabIndex={0}
                        aria-label="Show More Events"
                        onKeyDown={e => {
                            if (e.key === "Enter" || e.key === " ") {
                                setShowAll(true);
                            }
                        }}
                    >
                        Show More Events
                    </button>
                )}
            </div>
        </div >
    );
}
