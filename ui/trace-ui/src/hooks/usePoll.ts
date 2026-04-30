import { useEffect } from "react";

// Generic interval poll. Calls `tick` immediately on mount, then every
// `intervalMs`. Each tick receives `(cancelled, startTime)`:
//   - `cancelled()` — returns true after cleanup; tick should drop its
//     setState calls when this returns true (the in-flight await may resolve
//     after unmount).
//   - `startTime` — Date.now() captured once per effect lifetime; lets tick
//     compute elapsed time without closing over a stale ref.
//
// `deps` re-mount the effect when anything changes (capturing a fresh
// startTime + cancelled flag).
export function usePoll(
    tick: (cancelled: () => boolean, startTime: number) => void | Promise<void>,
    intervalMs: number,
    deps: ReadonlyArray<unknown>,
): void {
    useEffect(() => {
        const startTime = Date.now();
        let cancelled = false;
        const isCancelled = () => cancelled;
        void tick(isCancelled, startTime);
        const id = setInterval(() => void tick(isCancelled, startTime), intervalMs);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [intervalMs, ...deps]);
}
