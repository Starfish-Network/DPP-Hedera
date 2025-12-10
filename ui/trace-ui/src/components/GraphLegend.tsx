export function GraphLegend() {
    return (
        <div className="absolute top-3 left-3 bg-white rounded-md shadow px-4 py-2 text-sm border flex items-center gap-3">
            <div className="flex items-center gap-1">
                <span className="w-4 h-4 bg-blue-100 border border-blue-500 rounded inline-block" />
                <span className="ml-1">Upstream Flow</span>
            </div>
            <div className="flex items-center gap-1">
                <span className="w-4 h-4 bg-gray-50 border border-slate-500 rounded inline-block" />
                <span className="ml-1">Current Lot</span>
            </div>
            <div className="flex items-center gap-1">
                <span className="w-4 h-4 bg-green-100 border border-green-600 rounded inline-block" />
                <span className="ml-1">Downstream Flow</span>
            </div>
        </div>
    );
}