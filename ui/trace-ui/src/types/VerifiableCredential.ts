// credentialSubject arrives as a single object or a list depending on the
// Guardian policy block tree; accept both shapes.
export interface VerifiableCredential {
    "@context": string[];
    type: string[];
    issuer: string;
    issuanceDate: string;
    credentialSubject: Record<string, unknown> | Record<string, unknown>[];
    proof: { type: string; [k: string]: unknown };
}
