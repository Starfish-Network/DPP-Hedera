import { useState, type ReactNode } from "react";
import { useHealthPoll } from "./hooks/useHealthPoll";
import type { GuardianHealth, HealthStatus } from "./types/GuardianHealth";
import { GuardianDemo } from "./views/GuardianDemo";
import { TraceExplorer } from "./views/TraceExplorer";

type Tab = "trace" | "demo";

interface BadgeStyle {
    label: string;
    className: string;
}

const HEALTH_STYLES: Record<HealthStatus, BadgeStyle> = {
    ok: { label: "Guardian: ok", className: "bg-green-100 text-green-800" },
    breaker_open: { label: "Guardian: breaker open", className: "bg-amber-100 text-amber-800" },
    tos_required: { label: "Guardian: ToS required", className: "bg-amber-100 text-amber-800" },
    unavailable: { label: "Guardian: unavailable", className: "bg-gray-100 text-gray-700" },
};

function deriveBadge(apiOnline: boolean, health: GuardianHealth | null): BadgeStyle {
    if (!apiOnline) return { label: "API offline", className: "bg-red-100 text-red-800" };
    if (!health) return { label: "Guardian: …", className: "bg-gray-100 text-gray-700" };
    return HEALTH_STYLES[health.status];
}

export default function App() {
    const [tab, setTab] = useState<Tab>("trace");
    const { health, apiOnline } = useHealthPoll();
    const { label: healthLabel, className: healthClass } = deriveBadge(apiOnline, health);

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white border-b shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
                    <h1 className="text-xl font-bold whitespace-nowrap">🧭 DPP-Hedera</h1>
                    <nav className="flex gap-2">
                        <TabButton active={tab === "trace"} onClick={() => setTab("trace")}>
                            Trace Explorer
                        </TabButton>
                        <TabButton active={tab === "demo"} onClick={() => setTab("demo")}>
                            Guardian Demo
                        </TabButton>
                    </nav>
                    <span
                        className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${healthClass}`}
                        title="Live /api/v1/guardian/health"
                    >
                        {healthLabel}
                    </span>
                </div>
            </header>
            <main className="max-w-7xl mx-auto p-6">
                {tab === "trace" ? <TraceExplorer /> : <GuardianDemo />}
            </main>
        </div>
    );
}

function TabButton({
    active,
    onClick,
    children,
}: Readonly<{
    active: boolean;
    onClick: () => void;
    children: ReactNode;
}>) {
    return (
        <button
            onClick={onClick}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
                active
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
        >
            {children}
        </button>
    );
}
