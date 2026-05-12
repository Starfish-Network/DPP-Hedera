import { useEffect } from "react";

// Generic interval poll. Calls `tick` immediately on mount, then every
// `intervalMs`. Set `stopped: true` to suspend the loop without unmounting
// (e.g. once a poll has reached a terminal state). Each tick receives
// `(cancelled, startTime)`:
//   - `cancelled()` — returns true after cleanup; tick should drop its
//     setState calls when this returns true (the in-flight await may resolve
//     after unmount).
//   - `startTime` — Date.now() captured once per effect lifetime; lets tick
//     compute elapsed time without closing over a stale ref.
export function usePoll(
    tick: (cancelled: () => boolean, startTime: number) => void | Promise<void>,
    intervalMs: number,
    deps: ReadonlyArray<unknown>,
    stopped: boolean = false,
): void {
    useEffect(() => {
        if (stopped) return;
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
    }, [intervalMs, stopped, ...deps]);
}
