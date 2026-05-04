import type { VerifiableCredential } from "../types/VerifiableCredential";

// MGS-issued VCs land with `credentialSubject` either as a single object or
// as a list of objects, depending on the policy block tree that issued them.
// Normalise to a single subject for rendering — VCs we care about always have
// at most one in v1.
export function getSubject(vc: VerifiableCredential): Record<string, unknown> {
    const cs = vc.credentialSubject;
    if (Array.isArray(cs)) return cs[0] ?? {};
    return cs;
}
