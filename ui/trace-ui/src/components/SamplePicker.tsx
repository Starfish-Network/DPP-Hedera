interface Props<T> {
    items: Record<string, T>;
    selected: string;
    onSelect: (key: string) => void;
    label: string;
}

export function SamplePicker<T>({ items, selected, onSelect, label }: Readonly<Props<T>>) {
    const keys = Object.keys(items).sort((a, b) => a.localeCompare(b));

    if (keys.length === 0) {
        return <div className="text-sm text-gray-500 italic">No samples found.</div>;
    }

    const current = selected && items[selected] ? items[selected] : null;

    return (
        <div className="space-y-2">
            <label className="block text-sm font-semibold text-gray-700">{label}</label>
            <select
                value={selected}
                onChange={(e) => onSelect(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-2 w-full"
            >
                {keys.map((k) => (
                    <option key={k} value={k}>
                        {k}
                    </option>
                ))}
            </select>
            {current && (
                <details className="text-xs text-gray-600">
                    <summary className="cursor-pointer">Preview JSON</summary>
                    <pre className="mt-2 p-2 bg-gray-50 border rounded overflow-x-auto">
                        {JSON.stringify(current, null, 2)}
                    </pre>
                </details>
            )}
        </div>
    );
}
