import { Fragment } from "react";
import type { PolicySlug } from "../types/PolicySlug";
import type { VerifiableCredential } from "../types/VerifiableCredential";

interface Props {
    vc: VerifiableCredential;
    slug: PolicySlug;
}

function getSubject(vc: VerifiableCredential): Record<string, unknown> {
    const cs = vc.credentialSubject;
    if (Array.isArray(cs)) return cs[0] ?? {};
    return cs;
}

function formatScalar(v: unknown): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
        return String(v);
    }
    return JSON.stringify(v);
}

const FIELDS: Record<PolicySlug, Array<{ key: string; label: string }>> = {
    gdst: [
        { key: "gdstEventType", label: "Event Type" },
        { key: "complianceStatus", label: "Compliance Status" },
        { key: "policyVersion", label: "Policy Version" },
        { key: "issuedAt", label: "Issued At" },
        { key: "species", label: "Species (FAO ASFIS)" },
        { key: "supersedes", label: "Supersedes" },
    ],
    fsma: [
        { key: "fsma204EventType", label: "Event Type" },
        { key: "complianceStatus", label: "Compliance Status" },
        { key: "policyVersion", label: "Policy Version" },
        { key: "issuedAt", label: "Issued At" },
        { key: "supersedes", label: "Supersedes" },
    ],
};

export function GuaranteedFieldsCard({ vc, slug }: Readonly<Props>) {
    const subject = getSubject(vc);
    const fields = FIELDS[slug];
    return (
        <div className="border border-green-300 bg-green-50 rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-green-900">Verifiable Credential issued</h3>
            <dl className="grid grid-cols-[10rem_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="font-medium text-gray-600">Issuer</dt>
                <dd className="font-mono text-xs break-all">{vc.issuer}</dd>
                <dt className="font-medium text-gray-600">Event Hash</dt>
                <dd className="font-mono text-xs break-all">
                    {formatScalar(subject.eventHash)}
                </dd>
                {fields.map(({ key, label }) => {
                    const value = subject[key];
                    if (value === undefined || value === null) return null;
                    return (
                        <Fragment key={key}>
                            <dt className="font-medium text-gray-600">{label}</dt>
                            <dd className="text-gray-900 break-all">{formatScalar(value)}</dd>
                        </Fragment>
                    );
                })}
            </dl>
            <details className="text-xs text-gray-600">
                <summary className="cursor-pointer">Full credentialSubject</summary>
                <pre className="mt-2 p-2 bg-white border rounded overflow-x-auto text-[11px]">
                    {JSON.stringify(subject, null, 2)}
                </pre>
            </details>
        </div>
    );
}
