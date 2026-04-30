// Source: T048 + G1 fix in api/app/routes/{gdst/events,epcis/compliance}.py.
export type GuardianSubmissionStatus =
    | { status: "submitted"; cached: boolean; submittedAt: string }
    | { status: "skipped"; reason: "not_configured" | "not_compliant" | "breaker_open" }
    | { status: "error"; reason: string };

export interface ComplianceCheckResponse {
    contractId?: string;
    isCompliant: boolean;
    status?: string;
    txStatus?: string;
    eventHashHex: string;
    // Additive fields from the submit-route responses (T048 / G1):
    transactionId?: string;
    receiptStatus?: string;
    eventType?: string;
    eventHash?: string;
    source?: string;
    guardian?: GuardianSubmissionStatus;
}
