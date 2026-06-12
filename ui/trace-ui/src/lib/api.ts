import type { GDSTEvent } from "../types/GDSTEvent";
import type { GuardianHealth } from "../types/GuardianHealth";
import type { PolicySlug } from "../types/PolicySlug";
import type { StarfishEvent } from "../types/StarfishEvents";
import type { SubmitResponse } from "../types/SubmitResponse";
import type { VerifiableCredential } from "../types/VerifiableCredential";

export class ApiError extends Error {
    readonly status: number;
    readonly body: unknown;
    constructor(message: string, status: number, body: unknown) {
        super(message);
        this.status = status;
        this.body = body;
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(path, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) {
        let body: unknown = null;
        try {
            body = await res.json();
        } catch {
            // body wasn't JSON; carry on with null
        }
        throw new ApiError(`${path} → ${res.status}`, res.status, body);
    }
    return res.json() as Promise<T>;
}

export async function submitGdstEvent(
    event: GDSTEvent | Record<string, unknown>,
): Promise<SubmitResponse> {
    return request("/api/v1/gdst/events", {
        method: "POST",
        body: JSON.stringify(event),
    });
}

export async function submitFsmaEvent(event: StarfishEvent): Promise<SubmitResponse> {
    return request("/api/v1/epcis/compliance/check", {
        method: "POST",
        body: JSON.stringify(event),
    });
}

export async function submitGenericEvent(
    event: Record<string, unknown>,
): Promise<SubmitResponse> {
    return request("/api/v1/events", {
        method: "POST",
        body: JSON.stringify(event),
    });
}

export async function getVc(
    slug: PolicySlug,
    eventHash: string,
    opts: { history?: boolean } = {},
): Promise<VerifiableCredential | VerifiableCredential[] | null> {
    const qs = opts.history ? "?history=true" : "";
    try {
        return await request(`/api/v1/guardian/${slug}/vc/${eventHash}${qs}`);
    } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
    }
}

export async function getHealth(): Promise<GuardianHealth> {
    return request("/api/v1/guardian/health");
}

// MGS document envelope wrapping the policy's self-describing W3C VC under
// `.document`. Fetched from /guardian/{slug}/policy-vc; 404 returns null per
// FR-007 not-yet-issued semantics.
//
// Only the fields we render are declared. MGS returns extras (tenantId,
// createDate, _propHash, hash, owner, documentFileId, etc.) — add them
// here when a consumer needs one.
export interface PolicyVcEnvelope {
    readonly id: string;
    readonly type: string;
    readonly policyId: string;
    readonly hederaStatus?: string;
    readonly signature?: number;
    readonly document: VerifiableCredential;
}

export async function getPolicyVc(slug: PolicySlug): Promise<PolicyVcEnvelope | null> {
    try {
        return await request(`/api/v1/guardian/${slug}/policy-vc`);
    } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
    }
}

export async function injectBreakerFailure(): Promise<{ active: true }> {
    return request("/api/v1/_demo/breaker/inject", {
        method: "POST",
        body: "{}",
    });
}

export async function clearBreaker(): Promise<{ active: false }> {
    return request("/api/v1/_demo/breaker/clear", {
        method: "POST",
        body: "{}",
    });
}

export async function getBreakerSimulatorStatus(): Promise<{ active: boolean }> {
    return request("/api/v1/_demo/breaker/status");
}
