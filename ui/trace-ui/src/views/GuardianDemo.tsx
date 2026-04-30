import { useState } from "react";

type DemoTab = "submit_gdst" | "submit_fsma" | "health" | "retrieve" | "about";

const TABS: Array<{ id: DemoTab; label: string }> = [
    { id: "submit_gdst", label: "Submit GDST" },
    { id: "submit_fsma", label: "Submit FSMA" },
    { id: "health", label: "Health & Resilience" },
    { id: "retrieve", label: "Retrieve VC" },
    { id: "about", label: "About" },
];

export function GuardianDemo() {
    const [tab, setTab] = useState<DemoTab>("submit_gdst");
    const activeLabel = TABS.find((t) => t.id === tab)?.label ?? "";

    return (
        <div className="grid grid-cols-[12rem_1fr] gap-6">
            <aside className="space-y-1">
                {TABS.map((t) => (
                    <button
                        key={t.id}
                        onClick={() => setTab(t.id)}
                        className={`w-full text-left px-3 py-2 rounded-md font-medium transition-colors ${
                            tab === t.id
                                ? "bg-blue-100 text-blue-900"
                                : "text-gray-700 hover:bg-gray-100"
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </aside>
            <section className="bg-white border rounded-lg shadow p-6 min-h-[400px]">
                <Placeholder label={activeLabel} />
            </section>
        </div>
    );
}

interface PlaceholderProps {
    readonly label: string;
}

function Placeholder({ label }: PlaceholderProps) {
    return (
        <div className="text-gray-500 italic">
            <p className="mb-2">{label} — coming soon (Phase 3+).</p>
            <p className="text-sm">
                This page is part of the Guardian Demo for spec 002-demo-ui.
            </p>
        </div>
    );
}
