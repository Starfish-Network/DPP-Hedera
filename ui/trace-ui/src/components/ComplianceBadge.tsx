import type { GuardianSubmissionStatus } from "../types/ComplianceCheckResponse";

interface Props {
    isCompliant: boolean;
    guardian?: GuardianSubmissionStatus;
}

interface BadgeStyle {
    label: string;
    className: string;
}

function deriveStyle({ isCompliant, guardian }: Props): BadgeStyle {
    if (!isCompliant) {
        return {
            label: "Recorded — non-compliant",
            className: "bg-amber-100 text-amber-800 border-amber-300",
        };
    }
    if (!guardian || guardian.status === "skipped") {
        const reason =
            guardian?.status === "skipped" ? guardian.reason : "not_configured";
        return {
            label: `Recorded — Guardian ${reason.replaceAll("_", " ")}`,
            className: "bg-gray-100 text-gray-700 border-gray-300",
        };
    }
    if (guardian.status === "submitted") {
        return {
            label: "Compliant ✓",
            className: "bg-green-100 text-green-800 border-green-300",
        };
    }
    return {
        label: `Guardian error: ${guardian.reason}`,
        className: "bg-red-100 text-red-800 border-red-300",
    };
}

export function ComplianceBadge(props: Readonly<Props>) {
    const { label, className } = deriveStyle(props);
    return (
        <span
            className={`inline-block px-3 py-1 rounded-full border text-sm font-medium ${className}`}
        >
            {label}
        </span>
    );
}
