// Glob path is 4-up from this file because samples/ lives at the repo root,
// not inside ui/trace-ui/. Vite resolves it at build time.
import type { StarfishEvent } from "../types/StarfishEvents";

const gdstFiles = import.meta.glob<{ default: Record<string, unknown> }>(
    "../../../../samples/gdst/*.json",
    { eager: true },
);
const fsmaFiles = import.meta.glob<{ default: StarfishEvent }>(
    "../../../../samples/fsma/*.json",
    { eager: true },
);

function stem(path: string): string {
    const filename = path.split("/").pop() ?? "";
    return filename.replace(/\.json$/, "");
}

function asRecord<T>(files: Record<string, { default: T }>): Record<string, T> {
    const result: Record<string, T> = {};
    for (const [path, mod] of Object.entries(files)) {
        result[stem(path)] = mod.default;
    }
    return result;
}

export const gdstSamples: Record<string, Record<string, unknown>> = asRecord(gdstFiles);
export const fsmaSamples: Record<string, StarfishEvent> = asRecord(fsmaFiles);
