// Source of truth: api/app/routes/guardian/identity.py::HealthResponse.
export type HealthStatus = "ok" | "tos_required" | "breaker_open" | "unavailable";
export type BreakerState = "closed" | "open" | "half_open" | "tos_required";

export interface GuardianHealth {
    status: HealthStatus;
    breaker: BreakerState;
    last_failure_at: number | null;
}
