import type { GuardianSubmissionStatus } from "./ComplianceCheckResponse";

// Shape returned by POST /api/v1/gdst/events and /api/v1/epcis/compliance/check.
export interface SubmitResponse {
    status: "ok";
    transactionId: string;
    receiptStatus: string;
    eventType: string;
    eventHash: string;
    isCompliant: boolean;
    source: string;
    guardian: GuardianSubmissionStatus;
}
