import { useState } from "react";
import { getHealth } from "../lib/api";
import type { GuardianHealth } from "../types/GuardianHealth";
import { usePoll } from "./usePoll";

export interface UseHealthPollResult {
    health: GuardianHealth | null;
    apiOnline: boolean;
}

function sameHealth(a: GuardianHealth | null, b: GuardianHealth | null): boolean {
    if (a === b) return true;
    if (!a || !b) return false;
    return (
        a.status === b.status &&
        a.breaker === b.breaker &&
        a.last_failure_at === b.last_failure_at
    );
}

export function useHealthPoll(intervalMs: number = 5000): UseHealthPollResult {
    const [result, setResult] = useState<UseHealthPollResult>({
        health: null,
        apiOnline: true,
    });

    usePoll(
        async (cancelled) => {
            try {
                const health = await getHealth();
                if (cancelled()) return;
                setResult((prev) =>
                    sameHealth(prev.health, health) && prev.apiOnline
                        ? prev
                        : { health, apiOnline: true },
                );
            } catch {
                if (cancelled()) return;
                setResult((prev) =>
                    prev.apiOnline ? { health: prev.health, apiOnline: false } : prev,
                );
            }
        },
        intervalMs,
        [],
    );

    return result;
}
