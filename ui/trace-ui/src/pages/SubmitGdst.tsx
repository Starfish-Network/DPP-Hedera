import { useState } from "react";
import { ComplianceBadge } from "../components/ComplianceBadge";
import { GuaranteedFieldsCard } from "../components/GuaranteedFieldsCard";
import { SamplePicker } from "../components/SamplePicker";
import { usePollForVc, type PollState } from "../hooks/usePollForVc";
import { ApiError, submitGdstEvent } from "../lib/api";
import { gdstSamples } from "../lib/samples";
import type { GuardianSubmissionStatus } from "../types/ComplianceCheckResponse";
import type { SubmitResponse } from "../types/SubmitResponse";

export function SubmitGdst() {
    const sampleKeys = Object.keys(gdstSamples).sort((a, b) => a.localeCompare(b));
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
                <ResultPanel result={result} pollState={pollState} shouldPoll={shouldPoll} />
            )}
        </div>
    );
}

interface PydanticError {
    type: string;
    loc: (string | number)[];
    msg: string;
    input?: unknown;
}

function ErrorPanel({ error }: Readonly<{ error: ApiError | Error }>) {
    if (error instanceof ApiError && error.status === 422) {
        const body = error.body as { detail?: PydanticError[] } | null;
        const items = body?.detail ?? [];
        return (
            <div className="border border-red-300 bg-red-50 rounded-lg p-4 space-y-2">
                <h3 className="font-semibold text-red-900">Validation failed (422)</h3>
                <p className="text-sm text-red-800">
                    Pydantic rejected the event before any HCS write or Guardian
                    forwarding was attempted.
                </p>
                <ul className="text-sm text-red-800 list-disc list-inside space-y-1">
                    {items.map((d) => (
                        <li key={d.loc.join(".") + d.type}>
                            <code>{d.loc.join(".")}</code> — {d.msg}
                        </li>
                    ))}
                </ul>
            </div>
        );
    }
    if (error instanceof ApiError) {
        return (
            <div className="border border-red-300 bg-red-50 rounded-lg p-4 space-y-2">
                <h3 className="font-semibold text-red-900">API error ({error.status})</h3>
                <pre className="text-xs overflow-x-auto p-2 bg-white border rounded">
                    {JSON.stringify(error.body, null, 2)}
                </pre>
            </div>
        );
    }
    return (
        <div className="border border-red-300 bg-red-50 rounded-lg p-4">
            <h3 className="font-semibold text-red-900">Network error</h3>
            <p className="text-sm text-red-800 mt-1">{error.message}</p>
        </div>
    );
}

interface ResultPanelProps {
    readonly result: SubmitResponse;
    readonly pollState: PollState;
    readonly shouldPoll: boolean;
}

function ResultPanel({ result, pollState, shouldPoll }: ResultPanelProps) {
    return (
        <div className="space-y-4">
            <div className="bg-white border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <h3 className="font-semibold">HCS Receipt</h3>
                    <ComplianceBadge
                        isCompliant={result.isCompliant}
                        guardian={result.guardian}
                    />
                </div>
                <dl className="grid grid-cols-[10rem_1fr] gap-x-4 gap-y-1 text-sm">
                    <dt className="text-gray-600">Transaction ID</dt>
                    <dd className="font-mono text-xs">{result.transactionId}</dd>
                    <dt className="text-gray-600">Receipt Status</dt>
                    <dd>{result.receiptStatus}</dd>
                    <dt className="text-gray-600">Event Hash</dt>
                    <dd className="font-mono text-xs break-all">{result.eventHash}</dd>
                    <dt className="text-gray-600">Event Type</dt>
                    <dd>{result.eventType}</dd>
                </dl>
                <GuardianStatusInline guardian={result.guardian} />
            </div>

            {shouldPoll && pollState.status === "polling" && (
                <PollingPill elapsedMs={pollState.elapsedMs} />
            )}
            {shouldPoll && pollState.status === "manual_review" && <ManualReviewPanel />}
            {shouldPoll && pollState.status === "ready" && (
                <GuaranteedFieldsCard vc={pollState.vc} slug="gdst" />
            )}
        </div>
    );
}

function GuardianStatusInline({
    guardian,
}: Readonly<{ guardian: GuardianSubmissionStatus }>) {
    if (guardian.status === "submitted") {
        return (
            <p className="text-sm text-gray-600">
                Guardian: submitted{guardian.cached ? " (idempotency cache hit)" : ""} at{" "}
                <time>{guardian.submittedAt}</time>
            </p>
        );
    }
    if (guardian.status === "skipped") {
        const REASONS: Record<typeof guardian.reason, string> = {
            not_configured:
                "policy not configured — run scripts/build_gdst_policy.py and populate api/.env.dev",
            not_compliant:
                "rule predicate failed (gdst_min_rules returned False) — no VC will be issued",
            breaker_open:
                "circuit breaker is open — check the health badge in the header or query /api/v1/guardian/health directly",
        };
        return (
            <p className="text-sm text-gray-600">Guardian: skipped — {REASONS[guardian.reason]}.</p>
        );
    }
    return (
        <p className="text-sm text-red-700">Guardian error: {guardian.reason}</p>
    );
}

function PollingPill({ elapsedMs }: Readonly<{ elapsedMs: number }>) {
    const seconds = Math.floor(elapsedMs / 1000);
    return (
        <div className="border border-blue-300 bg-blue-50 rounded-lg p-3 flex items-center gap-3">
            <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full" />
            <span className="text-sm text-blue-900">Polling for VC… ({seconds}s)</span>
        </div>
    );
}

function ManualReviewPanel() {
    return (
        <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
            <p className="font-semibold text-amber-900">Manual review required</p>
            <p className="text-sm text-amber-800 mt-1">
                The VC didn't arrive within 5 minutes (SC-007 ceiling). Check the
                health badge in the page header for breaker state, or query{" "}
                <code>/api/v1/guardian/health</code> directly.
            </p>
        </div>
    );
}
