import { useMemo, useState } from "react";
import { ErrorPanel } from "../components/SubmitFlow";
import { SamplePicker } from "../components/SamplePicker";
import { ApiError, dryrunSubmit, type DryrunSubmitResponse } from "../lib/api";
import { fsmaSamples, gdstSamples } from "../lib/samples";
import type { PolicySlug } from "../types/PolicySlug";
import type { VerifiableCredential } from "../types/VerifiableCredential";
import { getSubject } from "../lib/vc";

const POLICY_OPTIONS: ReadonlyArray<{ slug: PolicySlug; label: string }> = [
    { slug: "gdst", label: "GDST" },
    { slug: "fsma", label: "FSMA" },
];

export function DryrunSubmit() {
    const [slug, setSlug] = useState<PolicySlug>("gdst");
    const samples = slug === "gdst" ? gdstSamples : fsmaSamples;
    const sampleKeys = useMemo(
        () => Object.keys(samples).sort((a, b) => a.localeCompare(b)),
        [samples],
    );
    const [selectedKey, setSelectedKey] = useState<string>(sampleKeys[0] ?? "");
    const [submitting, setSubmitting] = useState(false);
    const [response, setResponse] = useState<DryrunSubmitResponse | null>(null);
    const [error, setError] = useState<ApiError | Error | null>(null);

    function onSlugChange(next: PolicySlug) {
        setSlug(next);
        const nextSamples = next === "gdst" ? gdstSamples : fsmaSamples;
        const firstKey = Object.keys(nextSamples).sort((a, b) => a.localeCompare(b))[0];
        setSelectedKey(firstKey ?? "");
        setResponse(null);
        setError(null);
    }

    async function onSubmit() {
        if (!selectedKey) return;
        setSubmitting(true);
        setResponse(null);
        setError(null);
        // The dry-run schema only declares `marker` plus the Guardian-injected
        // fields (policyId, guardianVersion, ref). MGS publishes schemas with
        // `additionalProperties: false`, so sending the full GDST/FSMA event
        // would 422. We commit a tag identifying which sample was issued; the
        // demo value is the *signed VC* round-trip, not the rich subject.
        const marker = `${slug}-${selectedKey}-${Date.now()}`;
        try {
            const r = await dryrunSubmit(slug, { marker });
            setResponse(r);
        } catch (e) {
            setError(e instanceof Error ? e : new Error(String(e)));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold">Issue VC (dry-run)</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Submits to the dry-run sandbox policy via{" "}
                    <code>POST /api/v1/guardian/dryrun/submit/{"{slug}"}</code>. MGS runs
                    the chain (<code>requestVcDocumentBlock → sendToGuardianBlock</code>)
                    server-side and returns a real signed VC inline. Useful when the
                    published-policy worker is wedged.
                </p>
                <p className="text-xs text-gray-500 mt-1">
                    Configure the underlying policy with{" "}
                    <code>scripts/bootstrap_dryrun_policy.py</code> and set{" "}
                    <code>GUARDIAN_DRYRUN_POLICY_ID</code> +{" "}
                    <code>GUARDIAN_DRYRUN_INTAKE_BLOCK_TAG</code>.
                </p>
            </header>

            <div className="bg-white border rounded-lg p-4 space-y-4">
                <fieldset>
                    <legend className="text-sm font-semibold text-gray-700 mb-1">
                        Policy
                    </legend>
                    <div className="flex gap-4">
                        {POLICY_OPTIONS.map((opt) => (
                            <label key={opt.slug} className="flex items-center gap-2 text-sm">
                                <input
                                    type="radio"
                                    name="dryrun-slug"
                                    value={opt.slug}
                                    checked={slug === opt.slug}
                                    onChange={() => onSlugChange(opt.slug)}
                                />
                                {opt.label}
                            </label>
                        ))}
                    </div>
                </fieldset>

                <SamplePicker
                    items={samples}
                    selected={selectedKey}
                    onSelect={setSelectedKey}
                    label={`${slug.toUpperCase()} sample`}
                />

                <button
                    onClick={onSubmit}
                    disabled={submitting || !selectedKey}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                    {submitting ? "Issuing…" : "Issue VC"}
                </button>
            </div>

            {error && <ErrorPanel error={error} />}
            {response && <DryrunResultPanel response={response} />}
        </div>
    );
}

function DryrunResultPanel({ response }: Readonly<{ response: DryrunSubmitResponse }>) {
    const vc = response.vc;
    if (!vc) {
        return (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
                <p className="font-semibold text-amber-900">
                    Submission accepted but no VC returned
                </p>
                <p className="text-sm text-amber-800 mt-1">
                    MGS responded but the chain didn't produce a credential. The raw
                    response is below.
                </p>
                <pre className="mt-2 text-[11px] p-2 bg-white border rounded overflow-x-auto">
                    {JSON.stringify(response.raw, null, 2)}
                </pre>
            </div>
        );
    }
    return <DryrunVcCard vc={vc} policyId={response.policyId} />;
}

function DryrunVcCard({
    vc,
    policyId,
}: Readonly<{ vc: VerifiableCredential; policyId: string }>) {
    const proof = (vc as { proof?: { type?: string; jws?: string } }).proof ?? {};
    const subject = getSubject(vc);
    return (
        <div className="border border-green-300 bg-green-50 rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-green-900">Verifiable Credential issued</h3>
            <dl className="grid grid-cols-[10rem_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="font-medium text-gray-600">VC ID</dt>
                <dd className="font-mono text-xs break-all">{vc.id}</dd>
                <dt className="font-medium text-gray-600">Issuer</dt>
                <dd className="font-mono text-xs break-all">{vc.issuer}</dd>
                <dt className="font-medium text-gray-600">Issued At</dt>
                <dd>{vc.issuanceDate}</dd>
                <dt className="font-medium text-gray-600">Policy ID</dt>
                <dd className="font-mono text-xs break-all">{policyId}</dd>
                <dt className="font-medium text-gray-600">Proof</dt>
                <dd className="font-mono text-xs">{proof.type ?? "—"}</dd>
                <dt className="font-medium text-gray-600">JWS</dt>
                <dd className="font-mono text-[11px] break-all">
                    {proof.jws ? `${proof.jws.slice(0, 64)}…` : "—"}
                </dd>
            </dl>
            <details className="text-xs text-gray-600">
                <summary className="cursor-pointer">credentialSubject</summary>
                <pre className="mt-2 p-2 bg-white border rounded overflow-x-auto text-[11px]">
                    {JSON.stringify(subject, null, 2)}
                </pre>
            </details>
            <details className="text-xs text-gray-600">
                <summary className="cursor-pointer">Full VC</summary>
                <pre className="mt-2 p-2 bg-white border rounded overflow-x-auto text-[11px]">
                    {JSON.stringify(vc, null, 2)}
                </pre>
            </details>
        </div>
    );
}
