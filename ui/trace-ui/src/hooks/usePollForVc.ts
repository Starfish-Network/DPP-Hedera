import { useState } from "react";
import { ApiError, getVc } from "../lib/api";
import type { PolicySlug } from "../types/PolicySlug";
import type { VerifiableCredential } from "../types/VerifiableCredential";
import { usePoll } from "./usePoll";

export type PollState =
    | { status: "polling"; elapsedMs: number }
    | { status: "ready"; vc: VerifiableCredential; elapsedMs: number }
    | { status: "manual_review"; elapsedMs: number };

interface Options {
    intervalMs?: number;
    timeoutMs?: number;
}

export function usePollForVc(
    slug: PolicySlug | null,
    eventHash: string | null,
    opts: Options = {},
): PollState {
    const intervalMs = opts.intervalMs ?? 5000;
    const timeoutMs = opts.timeoutMs ?? 300_000;
    const [state, setState] = useState<PollState>({ status: "polling", elapsedMs: 0 });

    usePoll(
        async (cancelled, startTime) => {
            if (!slug || !eventHash) return;
            const elapsedMs = Date.now() - startTime;
            if (elapsedMs >= timeoutMs) {
                if (!cancelled()) setState({ status: "manual_review", elapsedMs });
                return;
            }
            try {
                const result = await getVc(slug, eventHash);
                if (cancelled()) return;
                if (result && !Array.isArray(result)) {
                    setState({ status: "ready", vc: result, elapsedMs });
                    return;
                }
            } catch (e) {
                if (!(e instanceof ApiError && e.status === 404)) {
                    console.error("[usePollForVc]", e);
                }
            }
            if (!cancelled()) setState({ status: "polling", elapsedMs });
        },
        intervalMs,
        [slug, eventHash, timeoutMs],
    );

    return state;
}
