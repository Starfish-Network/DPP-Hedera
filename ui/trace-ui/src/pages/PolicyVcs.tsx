import { useEffect, useState } from "react";
import { ErrorPanel } from "../components/SubmitFlow";
import { ApiError, getPolicyVc, type PolicyVcEnvelope } from "../lib/api";
import { getSubject } from "../lib/vc";
import type { PolicySlug } from "../types/PolicySlug";

type SlotState =
    | { status: "loading" }
    | { status: "ready"; envelope: PolicyVcEnvelope }
    | { status: "not_found" }
    | { status: "error"; error: ApiError | Error };

const SLUGS: ReadonlyArray<{ slug: PolicySlug; label: string }> = [
    { slug: "gdst", label: "GDST" },
    { slug: "fsma", label: "FSMA 204" },
];

// Per-policy palette so each Policy VC card is visually distinct.
const PALETTE: Record<PolicySlug, { card: string; title: string; meta: string }> = {
    gdst: {
        card: "border-blue-300 bg-blue-50",
        title: "text-blue-900",
        meta: "text-blue-700",
    },
    fsma: {
        card: "border-green-300 bg-green-50",
        title: "text-green-900",
        meta: "text-green-700",
    },
};

export function PolicyVcs() {
    const [slots, setSlots] = useState<Record<PolicySlug, SlotState>>({
        gdst: { status: "loading" },
        fsma: { status: "loading" },
    });

    useEffect(() => {
        let cancelled = false;
        async function loadOne(slug: PolicySlug) {
            try {
                const env = await getPolicyVc(slug);
                if (cancelled) return;
                setSlots((prev) => ({
                    ...prev,
                    [slug]: env ? { status: "ready", envelope: env } : { status: "not_found" },
                }));
            } catch (e) {
                if (cancelled) return;
                setSlots((prev) => ({
                    ...prev,
                    [slug]: { status: "error", error: e instanceof Error ? e : new Error(String(e)) },
                }));
            }
        }
        SLUGS.forEach((opt) => void loadOne(opt.slug));
        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold">Policy Verifiable Credentials</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Each Guardian policy publishes a self-describing W3C Verifiable
                    Credential when it lands on Hedera, signed by the Standard Registry
                    DID. These are the canonical attestations that GDST and FSMA 204
                    rule sets are live on testnet — the issuer DID and IPFS-anchored
                    policy artefact are auditable independently of this app. Fetched
                    via{" "}
                    <code>GET /api/v1/guardian/{"{slug}"}/policy-vc</code>.
                </p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {SLUGS.map((opt) => (
                    <PolicyVcCard key={opt.slug} slug={opt.slug} label={opt.label} state={slots[opt.slug]} />
                ))}
            </div>
        </div>
    );
}

interface CardProps {
    readonly slug: PolicySlug;
    readonly label: string;
    readonly state: SlotState;
}

function PolicyVcCard({ slug, label, state }: CardProps) {
    if (state.status === "loading") {
        return (
            <div className="border rounded-lg p-4 bg-white text-sm text-gray-500 italic">
                Loading {label} policy VC…
            </div>
        );
    }
    if (state.status === "not_found") {
        return (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
                <h3 className="font-semibold text-amber-900">{label} policy not configured</h3>
                <p className="text-sm text-amber-800 mt-1">
                    No POLICY-type VC found. Run <code>scripts/build_{slug}_policy.py</code>{" "}
                    and populate <code>GUARDIAN_{slug.toUpperCase()}_POLICY_ID</code> in{" "}
                    <code>api/.env.dev</code>.
                </p>
            </div>
        );
    }
    if (state.status === "error") {
        return (
            <div className="space-y-2">
                <h3 className="font-semibold text-red-900">{label} policy VC unavailable</h3>
                <ErrorPanel error={state.error} />
            </div>
        );
    }

    const env = state.envelope;
    const vc = env.document;
    const cs = getSubject(vc);
    const ipfsCid = typeof cs.cid === "string" ? cs.cid : null;
    const palette = PALETTE[slug];

    return (
        <div className={`border rounded-lg p-4 space-y-3 ${palette.card}`}>
            <div className="flex items-baseline justify-between gap-2 flex-wrap">
                <h3 className={`font-semibold ${palette.title}`}>
                    {typeof cs.name === "string" ? cs.name : label}
                </h3>
                <span className={`text-xs uppercase tracking-wide ${palette.meta}`}>
                    POLICY · v{typeof cs.version === "string" ? cs.version : "?"}
                </span>
            </div>
            {typeof cs.description === "string" && (
                <p className="text-sm text-gray-700">{cs.description}</p>
            )}
            <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="text-gray-600">Policy tag</dt>
                <dd className="font-mono text-xs break-all">
                    {typeof cs.policyTag === "string" ? cs.policyTag : "—"}
                </dd>
                <dt className="text-gray-600">Issuer DID</dt>
                <dd className="font-mono text-xs break-all">{vc.issuer}</dd>
                <dt className="text-gray-600">Issued</dt>
                <dd className="text-xs">{vc.issuanceDate}</dd>
                <dt className="text-gray-600">Policy ID</dt>
                <dd className="font-mono text-xs break-all">{env.policyId}</dd>
                {ipfsCid && (
                    <>
                        <dt className="text-gray-600">IPFS</dt>
                        <dd className="text-xs break-all">
                            <a
                                href={`https://ipfs.io/ipfs/${ipfsCid}`}
                                target="_blank"
                                rel="noreferrer"
                                className={`hover:underline font-mono ${palette.meta}`}
                            >
                                {ipfsCid}
                            </a>
                        </dd>
                    </>
                )}
            </dl>
            <details className="text-xs text-gray-600">
                <summary className="cursor-pointer">Full credential</summary>
                <pre className="mt-2 p-2 bg-white border rounded overflow-x-auto text-[11px]">
                    {JSON.stringify(vc, null, 2)}
                </pre>
            </details>
        </div>
    );
}
