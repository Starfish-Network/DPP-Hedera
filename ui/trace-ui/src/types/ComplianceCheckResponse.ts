export interface ComplianceCheckResponse {
    contractId?: string;
    isCompliant: boolean;
    status?: string;
    txStatus?: string;
    eventHashHex: string;
}