import type { PollState } from "../hooks/usePollForVc";
import { ApiError } from "../lib/api";
import type { GuardianSubmissionStatus } from "../types/ComplianceCheckResponse";
import type { PolicySlug } from "../types/PolicySlug";
import type { SubmitResponse } from "../types/SubmitResponse";
import { ComplianceBadge } from "./ComplianceBadge";
import { GuaranteedFieldsCard } from "./GuaranteedFieldsCard";

interface PydanticError {
    type: string;
    loc: (string | number)[];
    msg: string;
    input?: unknown;
}

export function ErrorPanel({ error }: Readonly<{ error: ApiError | Error }>) {
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
    readonly slug: PolicySlug;
}

export function SubmitResultPanel({ result, pollState, slug }: ResultPanelProps) {
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
                <GuardianStatusInline guardian={result.guardian} slug={slug} />
            </div>

            {pollState.status === "polling" && (
                <PollingPill elapsedMs={pollState.elapsedMs} />
            )}
            {pollState.status === "manual_review" && <ManualReviewPanel />}
            {pollState.status === "ready" && (
                <GuaranteedFieldsCard vc={pollState.vc} slug={slug} />
            )}
        </div>
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

const BUILD_SCRIPT: Record<PolicySlug, string> = {
    gdst: "scripts/build_gdst_policy.py",
    fsma: "scripts/build_fsma_policy.py",
};

const RULE_PREDICATE: Record<PolicySlug, string> = {
    gdst: "gdst_min_rules",
    fsma: "fsma_min_rules",
};

function GuardianStatusInline({
    guardian,
    slug,
}: Readonly<{ guardian: GuardianSubmissionStatus; slug: PolicySlug }>) {
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
            not_configured: `policy not configured — run ${BUILD_SCRIPT[slug]} and populate api/.env.dev`,
            not_compliant: `rule predicate failed (${RULE_PREDICATE[slug]} returned False) — no VC will be issued`,
            breaker_open:
                "circuit breaker is open — check the health badge in the header or query /api/v1/guardian/health directly",
        };
        return (
            <p className="text-sm text-gray-600">
                Guardian: skipped — {REASONS[guardian.reason]}.
            </p>
        );
    }
    return <p className="text-sm text-red-700">Guardian error: {guardian.reason}</p>;
}
