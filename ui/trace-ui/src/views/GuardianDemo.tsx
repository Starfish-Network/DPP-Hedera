import { useState } from "react";
import { PolicyVcs } from "../pages/PolicyVcs";
import { SubmitFsma } from "../pages/SubmitFsma";
import { SubmitGdst } from "../pages/SubmitGdst";

// "retrieve" tab is hidden pending event-VC issuance fix in MGS — re-add it
// (and its import + render branch) once the policy chain emits VCs. The
// `pages/RetrieveVc.tsx` file is intentionally left in place.
type DemoTab = "policies" | "submit_gdst" | "submit_fsma";

const TABS: Array<{ id: DemoTab; label: string }> = [
    { id: "policies", label: "Policy VCs" },
    { id: "submit_gdst", label: "Submit GDST" },
    { id: "submit_fsma", label: "Submit FSMA" },
];

export function GuardianDemo() {
    const [tab, setTab] = useState<DemoTab>("policies");

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
                {tab === "policies" && <PolicyVcs />}
                {tab === "submit_gdst" && <SubmitGdst />}
                {tab === "submit_fsma" && <SubmitFsma />}
            </section>
        </div>
    );
}
