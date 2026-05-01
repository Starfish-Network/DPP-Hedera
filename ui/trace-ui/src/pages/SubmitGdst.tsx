import { useMemo, useState } from "react";
import { ErrorPanel, SubmitResultPanel } from "../components/SubmitFlow";
import { SamplePicker } from "../components/SamplePicker";
import { usePollForVc } from "../hooks/usePollForVc";
import { ApiError, submitGdstEvent } from "../lib/api";
import { gdstSamples } from "../lib/samples";
import type { SubmitResponse } from "../types/SubmitResponse";

export function SubmitGdst() {
    const sampleKeys = useMemo(
        () => Object.keys(gdstSamples).sort((a, b) => a.localeCompare(b)),
        [],
    );
    const [selectedKey, setSelectedKey] = useState<string>(sampleKeys[0] ?? "");
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<SubmitResponse | null>(null);
    const [error, setError] = useState<ApiError | Error | null>(null);

    // Only poll when Guardian actually accepted the document. Non-compliant
    // events get HCS-recorded but Guardian skips them — no VC will ever appear.
    const shouldPoll =
        result !== null &&
        result.isCompliant &&
        result.guardian.status === "submitted";

    const pollState = usePollForVc(
        shouldPoll ? "gdst" : null,
        shouldPoll ? result.eventHash : null,
    );

    async function onSubmit() {
        const sample = selectedKey ? gdstSamples[selectedKey] : null;
        if (!sample) return;
        setSubmitting(true);
        setResult(null);
        setError(null);
        try {
            const r = await submitGdstEvent(sample);
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
                <h2 className="text-2xl font-bold">Submit GDST event</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Pick one of the {sampleKeys.length} canonical GDST CTE samples from{" "}
                    <code>samples/gdst/</code> and submit it via{" "}
                    <code>POST /api/v1/gdst/events</code>. Watch the response stages:
                    Pydantic validation → HCS receipt → Guardian forwarding → issued VC.
                </p>
            </header>

            <div className="bg-white border rounded-lg p-4 space-y-3">
                <SamplePicker
                    items={gdstSamples}
                    selected={selectedKey}
                    onSelect={setSelectedKey}
                    label="GDST sample"
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
                <SubmitResultPanel
                    result={result}
                    pollState={pollState}
                    shouldPoll={shouldPoll}
                    slug="gdst"
                />
            )}
        </div>
    );
}
