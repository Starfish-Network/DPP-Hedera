import { useMemo, useState } from "react";
import { ErrorPanel, SubmitResultPanel } from "../components/SubmitFlow";
import { SamplePicker } from "../components/SamplePicker";
import { usePollForVc } from "../hooks/usePollForVc";
import { ApiError, submitFsmaEvent } from "../lib/api";
import { fsmaSamples } from "../lib/samples";
import type { SubmitResponse } from "../types/SubmitResponse";

export function SubmitFsma() {
    const sampleKeys = useMemo(
        () => Object.keys(fsmaSamples).sort((a, b) => a.localeCompare(b)),
        [],
    );
    const [selectedKey, setSelectedKey] = useState<string>(sampleKeys[0] ?? "");
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<SubmitResponse | null>(null);
    const [error, setError] = useState<ApiError | Error | null>(null);

    const eventHashToPoll =
        result?.guardian.status === "submitted" && result.isCompliant
            ? result.eventHash
            : null;
    const pollState = usePollForVc(eventHashToPoll ? "fsma" : null, eventHashToPoll);

    async function onSubmit() {
        const sample = selectedKey ? fsmaSamples[selectedKey] : null;
        if (!sample) return;
        setSubmitting(true);
        setResult(null);
        setError(null);
        try {
            const r = await submitFsmaEvent(sample);
            setResult(r);
        } catch (e) {
            setError(e instanceof Error ? e : new Error(String(e)));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold">Submit FSMA event</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Pick one of the {sampleKeys.length} canonical FSMA 204 event samples
                    from <code>samples/fsma/</code> and submit it via{" "}
                    <code>POST /api/v1/epcis/compliance/check</code>. The UI surfaces
                    the HCS receipt and Guardian forwarding status.
                </p>
            </header>

            <div className="bg-white border rounded-lg p-4 space-y-3">
                <SamplePicker
                    items={fsmaSamples}
                    selected={selectedKey}
                    onSelect={setSelectedKey}
                    label="FSMA sample"
                />
                <button
                    onClick={onSubmit}
                    disabled={submitting || !selectedKey}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                    {submitting ? "Submitting…" : "Submit"}
                </button>
            </div>

            {error && <ErrorPanel error={error} />}
            {result && (
                <SubmitResultPanel result={result} pollState={pollState} slug="fsma" />
            )}
        </div>
    );
}
