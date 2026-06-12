import { useMemo, useState } from "react";
import { ErrorPanel, SubmitResultPanel } from "../components/SubmitFlow";
import { SamplePicker } from "../components/SamplePicker";
import { usePollForVc } from "../hooks/usePollForVc";
import { ApiError, submitGenericEvent } from "../lib/api";
import { genericSamples } from "../lib/samples";
import type { SubmitResponse } from "../types/SubmitResponse";

// Backed by the generic Guardian policy. Posts to /api/v1/events which
// validates a minimum shape (event_type non-empty + event_time + ≤256 KB) and
// forwards the rest verbatim under the issued VC's `credentialSubject.event`.
// While the underlying policy is in DRY-RUN, issued VCs are real signed
// credentials but not anchored on Hedera.
export function SubmitGeneric() {
    const sampleKeys = useMemo(
        () => Object.keys(genericSamples).sort((a, b) => a.localeCompare(b)),
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
    const pollState = usePollForVc(eventHashToPoll ? "generic" : null, eventHashToPoll);

    async function onSubmit() {
        const sample = selectedKey ? genericSamples[selectedKey] : null;
        if (!sample) return;
        setSubmitting(true);
        setResult(null);
        setError(null);
        try {
            const r = await submitGenericEvent(sample);
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
                <h2 className="text-2xl font-bold">Submit generic event</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Pick one of the {sampleKeys.length} canonical generic samples from{" "}
                    <code>samples/generic/</code> and submit it via{" "}
                    <code>POST /api/v1/events</code>. The route validates the minimum
                    shape (<code>event_type</code> + <code>event_time</code>, ≤256 KB)
                    and forwards the rest verbatim under{" "}
                    <code>credentialSubject.event</code>.
                </p>
            </header>

            <div className="bg-white border rounded-lg p-4 space-y-3">
                <SamplePicker
                    items={genericSamples}
                    selected={selectedKey}
                    onSelect={setSelectedKey}
                    label="Generic event sample"
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
                <SubmitResultPanel result={result} pollState={pollState} slug="generic" />
            )}
        </div>
    );
}
