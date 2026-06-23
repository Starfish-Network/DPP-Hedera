"""Ingest an EPCIS event xlsx into Hedera via the DPP-Hedera API.

Each row becomes a Starfish EPCIS event POSTed to `/epcis/events`, which
envelope-encrypts it and writes it to the configured HCS topic (mainnet when
the API's .env has NETWORK=mainnet). The xlsx is just the data source; the
file itself is never uploaded.

Column map (sheet headers -> StarfishEvent):
    Event type        CREATING/SHIPPING/TRANSFORMING -> creating/shipping/transforming
    biz_location      CreatingEvent.biz_location / TransformingEvent.facility
    date + time + timezone_offset -> event_time (ISO-8601 with offset)
    epc, quantity, uom -> QuantityItem
    ship_from/ship_to -> ShippingEvent endpoints; TRANSFORMING uses ship_from
                         as the input EPC and epc/ship_to as the output EPC.

TRANSFORMING rows carry only the output quantity, so input quantities are
resolved by looking the input EPC up against its earlier creating/transform
quantity in the same sheet.

Run (openpyxl pulled in at runtime; httpx is a project dep):
    uv run --with openpyxl python scripts/ingest_xlsx.py --dry-run     # validate only
    uv run --with openpyxl python scripts/ingest_xlsx.py               # post to API
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable (local validation) regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import openpyxl

COLS = {
    "event_type": 0, "biz_location": 1, "date": 2, "time": 3, "tz": 4,
    "epc": 5, "quantity": 6, "uom": 7, "ship_from": 8, "ship_to": 9,
}


def _event_time(date, time, tz) -> str:
    """Combine the date cell, time string and offset into ISO-8601."""
    return f"{date.date().isoformat()}T{time}{tz}"


def read_rows(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    return [
        {k: r[i] for k, i in COLS.items()}
        for r in rows[1:]
        if r[COLS["event_type"]] is not None
    ]


def build_quantity_index(rows: list[dict]) -> dict[str, float]:
    """Map each EPC to its known quantity (primary EPC of any row), so
    TRANSFORMING input items can be resolved from prior rows."""
    return {r["epc"]: r["quantity"] for r in rows if r["epc"] is not None}


def to_payload(row: dict, qty_index: dict[str, float]) -> dict:
    etype = str(row["event_type"]).strip().upper()
    event_time = _event_time(row["date"], row["time"], row["tz"])
    base = {"event_time": event_time, "event_timezone_offset": row["tz"]}
    item = {
        "epc": row["epc"],
        "quantity": float(row["quantity"]),
        "unit_of_measurement": row["uom"],
    }

    if etype == "CREATING":
        return {**base, "eventType": "creating",
                "biz_location": row["biz_location"], "quantity_list": [item]}

    if etype == "SHIPPING":
        return {**base, "eventType": "shipping",
                "ship_from": row["ship_from"], "ship_to": row["ship_to"],
                "items": [item]}

    if etype == "TRANSFORMING":
        input_epc = row["ship_from"]
        input_item = {
            "epc": input_epc,
            "quantity": float(qty_index.get(input_epc, row["quantity"])),
            "unit_of_measurement": row["uom"],
        }
        return {**base, "eventType": "transforming",
                "facility": row["biz_location"],
                "transformation_id": f"{input_epc}->{row['epc']}",
                "input_items": [input_item], "output_items": [item]}

    raise ValueError(f"Unknown event type: {row['event_type']!r}")


def validate_local(payloads: list[dict]) -> None:
    """Validate against the real API models before spending any HBAR."""
    from pydantic import TypeAdapter
    from app.models.starfish_events import StarfishEvent

    adapter = TypeAdapter(StarfishEvent)
    for i, p in enumerate(payloads, 1):
        adapter.validate_python(p)
    print(f"OK: {len(payloads)} payloads valid against StarfishEvent")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default="nordpesca_events_transformed.xlsx")
    ap.add_argument("--api-url", default="http://localhost:8000/api/v1")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate + print payloads; do not POST.")
    ap.add_argument("--limit", type=int, default=0, help="Only process N rows.")
    ap.add_argument("--skip", type=int, default=0,
                    help="Skip the first N data rows (e.g. --skip 1 to resume after row 1).")
    args = ap.parse_args()

    all_rows = read_rows(args.file)
    rows = all_rows[args.skip:]
    if args.limit:
        rows = rows[: args.limit]
    qty_index = build_quantity_index(all_rows)
    payloads = [to_payload(r, qty_index) for r in rows]

    validate_local(payloads)

    if args.dry_run:
        import json
        for p in payloads:
            print(json.dumps(p))
        print(f"\nDRY RUN: {len(payloads)} events not posted.")
        return 0

    url = f"{args.api_url}/epcis/events"
    ok = 0
    with httpx.Client(timeout=60.0) as client:
        for i, p in enumerate(payloads, 1):
            try:
                resp = client.post(url, json=p)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(f"[{i}/{len(payloads)}] FAILED {p['eventType']} {p.get('event_time')}: "
                      f"{e.response.status_code} {e.response.text}", file=sys.stderr)
                continue
            body = resp.json()
            ok += 1
            print(f"[{i}/{len(payloads)}] {p['eventType']:12} "
                  f"tx={body.get('transactionId')} hash={body.get('eventHash')}")

    print(f"\nPosted {ok}/{len(payloads)} events to {url}")
    return 0 if ok == len(payloads) else 1


if __name__ == "__main__":
    raise SystemExit(main())
