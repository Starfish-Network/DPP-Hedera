import { useState } from "react";
import { GuaranteedFieldsCard } from "../components/GuaranteedFieldsCard";
import { ApiError, getVc } from "../lib/api";
import type { PolicySlug } from "../types/PolicySlug";
import type { VerifiableCredential } from "../types/VerifiableCredential";

type RetrievalState =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "not_found" }
    | { status: "single"; vc: VerifiableCredential }
    | { status: "error"; error: ApiError | Error };

export function RetrieveVc() {
    const [hash, setHash] = useState("");
    const [slug, setSlug] = useState<PolicySlug>("gdst");
    const [state, setState] = useState<RetrievalState>({ status: "idle" });

    async function onRetrieve() {
        if (!hash.trim()) return;
        setState({ status: "loading" });
        try {
            const result = await getVc(slug, hash.trim().replace(/^0x/, ""));
            if (result === null) {
                setState({ status: "not_found" });
                return;
            }
            if (Array.isArray(result)) {
                // history=false should always return a single VC, but defend against
                // a backend regression by collapsing to the latest entry.
                const latest = result[result.length - 1];
                if (latest) setState({ status: "single", vc: latest });
                else setState({ status: "not_found" });
            } else {
                setState({ status: "single", vc: result });
            }
        } catch (e) {
            setState({ status: "error", error: e instanceof Error ? e : new Error(String(e)) });
        }
    }

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold">Retrieve VC by event hash</h2>
                <p className="text-sm text-gray-600 mt-1">
                    Paste an <code>eventHash</code> from a prior submission (the Submit
                    pages copy it onto the result card) and fetch the issued VC via{" "}
                    <code>GET /api/v1/guardian/{"{slug}"}/vc/{"{eventHash}"}</code>.
                </p>
            </header>

            <div className="bg-white border rounded-lg p-4 space-y-4">
                <div>
                    <label
                        htmlFor="vc-hash-input"
                        className="block text-sm font-medium text-gray-700 mb-1"
                    >
                        Event hash (hex, 0x-prefixed or bare)
                    </label>
                    <input
                        id="vc-hash-input"
                        type="text"
                        value={hash}
                        onChange={(e) => setHash(e.target.value)}
                        placeholder="0x… or 64 hex chars"
                        className="w-full font-mono text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                </div>

                <fieldset>
                    <legend className="text-sm font-medium text-gray-700 mb-1">Policy</legend>
                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 text-sm">
                            <input
                                type="radio"
                                name="vc-slug"
                                value="gdst"
                                checked={slug === "gdst"}
                                onChange={() => setSlug("gdst")}
                            />
                            GDST
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                            <input
                                type="radio"
                                name="vc-slug"
                                value="fsma"
                                checked={slug === "fsma"}
                                onChange={() => setSlug("fsma")}
                            />
                            FSMA
                        </label>
                    </div>
                </fieldset>

                <button
                    onClick={onRetrieve}
                    disabled={!hash.trim() || state.status === "loading"}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                    {state.status === "loading" ? "Retrieving…" : "Retrieve"}
                </button>
            </div>

            <ResultPanel state={state} slug={slug} />
        </div>
    );
}

function ResultPanel({
    state,
    slug,
}: Readonly<{ state: RetrievalState; slug: PolicySlug }>) {
    if (state.status === "idle" || state.status === "loading") return null;

    if (state.status === "not_found") {
        return (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
                <p className="font-semibold text-amber-900">No VC for that event hash.</p>
                <p className="text-sm text-amber-800 mt-1">
                    Confirm you've submitted the event first (the Submit page copies
                    the <code>eventHash</code> onto the result card). Note: a non-compliant
                    submission gets HCS-recorded but Guardian skips it — no VC is ever
                    issued, and this lookup will keep returning empty.
                </p>
            </div>
        );
    }

    if (state.status === "error") {
        const err = state.error;
        if (err instanceof ApiError) {
            return (
                <div className="border border-red-300 bg-red-50 rounded-lg p-4 space-y-2">
                    <h3 className="font-semibold text-red-900">API error ({err.status})</h3>
                    <pre className="text-xs overflow-x-auto p-2 bg-white border rounded">
                        {JSON.stringify(err.body, null, 2)}
                    </pre>
                </div>
            );
        }
        return (
            <div className="border border-red-300 bg-red-50 rounded-lg p-4">
                <h3 className="font-semibold text-red-900">Network error</h3>
                <p className="text-sm text-red-800 mt-1">{err.message}</p>
            </div>
        );
    }

    return <GuaranteedFieldsCard vc={state.vc} slug={slug} />;
}
