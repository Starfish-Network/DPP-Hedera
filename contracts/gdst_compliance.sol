pragma solidity ^0.8.20;

contract GDSTEventRegistry {

    enum EventType {
        Unknown,
        Fishing,
        OnVesselProcessing,
        Transshipment,
        Landing,
        ShippingReceiving,
        Processing,
        AggregationDisaggregation
    }

    struct EventRecord {
        bytes32 payloadHash;     // SHA-256 hash of the GDST event payload
        EventType eventType;     // GDST event type
        uint256 eventTime;       // UNIX timestamp from payload
        address submitter;       // who wrote it to chain
        bytes32 parent;          // optional linkage (lot, prior event, etc.)
        uint256 blockTime;       // block timestamp when recorded
    }

    mapping(bytes32 => EventRecord) public events;

    event EventRecorded(
        bytes32 indexed payloadHash,
        EventType indexed eventType,
        address indexed submitter,
        bytes32 parent
    );

    function recordEvent(
        bytes32 payloadHash,
        EventType eventType,
        uint256 eventTime,
        bytes32 parent
    ) external {

        require(payloadHash != bytes32(0), "Invalid hash");
        require(eventTime > 0, "Invalid event time");
        require(eventType != EventType.Unknown, "Invalid event type");

        // Prevent overwriting
        require(events[payloadHash].payloadHash == 0, "Already exists");

        // Optional: enforce chronological linkage
        if (parent != 0) {
            require(events[parent].payloadHash != 0, "Parent not found");
            require(eventTime >= events[parent].eventTime, "Time must advance");
        }

        events[payloadHash] = EventRecord({
            payloadHash: payloadHash,
            eventType: eventType,
            eventTime: eventTime,
            submitter: msg.sender,
            parent: parent,
            blockTime: block.timestamp
        });

        emit EventRecorded(payloadHash, eventType, msg.sender, parent);
    }
}
