// Quantity Item
export interface QuantityItem {
    epc: string; // e.g., "urn:epc:class:lgtin:9506000.1233.a"
    quantity: number; // e.g., 12.0
    unit_of_measurement: string; // e.g., "kg"
}

// Base Event
export interface BaseEvent {
    event_time: string; // ISO timestamp, e.g., "2025-10-03T12:08:00.000Z"
    event_timezone_offset: string; // e.g., "+01:00"
}

// Creating Event
export interface CreatingEvent extends BaseEvent {
    eventType: "creating";
    biz_location: string; // e.g., "9506001112229"
    quantity_list: QuantityItem[];
}

// Shipping Event
export interface ShippingEvent extends BaseEvent {
    eventType: "shipping";
    ship_from: string;
    ship_to: string;
    items: QuantityItem[];
}

// Receiving Event
export interface ReceivingEvent extends BaseEvent {
    eventType: "receiving";
    shipped_from: string;
    received_at: string;
    items: QuantityItem[];
}

// Transforming Event
export interface TransformingEvent extends BaseEvent {
    eventType: "transforming";
    facility: string;
    transformation_id?: string | null;
    input_items: QuantityItem[];
    output_items: QuantityItem[];
}

// Packing Event
export interface PackingEvent extends BaseEvent {
    eventType: "packing";
    facility: string;
    container_id: string;
    input_items: QuantityItem[];
}

// Unpacking Event
export interface UnpackingEvent extends BaseEvent {
    eventType: "unpacking";
    facility: string;
    container_id: string;
    output_items: QuantityItem[];
}

// Discriminated union
export type StarfishEvent =
    | CreatingEvent
    | ShippingEvent
    | ReceivingEvent
    | TransformingEvent
    | PackingEvent
    | UnpackingEvent;
