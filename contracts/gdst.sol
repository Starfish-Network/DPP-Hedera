pragma solidity ^0.8.20;

contract ComplianceVerifier {
    struct ComplianceRecord {
        string eventType;
        bool isCompliant;
        uint256 timestamp;
        address verifiedBy;
    }

    mapping(bytes32 => ComplianceRecord) private records;
    bytes32[] private recordedEvents;

    mapping(bytes32 => string[]) public eventFiles;
    mapping(string => bytes32) public cidDataKeys;

    event ComplianceRecorded(
        bytes32 indexed eventHash,
        string eventType,
        bool isCompliant,
        address verifiedBy,
        uint256 timestamp
    );

    function recordEvent(bytes32 eventHash, string calldata eventType, bool isCompliant) external {
        require(records[eventHash].timestamp == 0, "Event already recorded");

        records[eventHash] = ComplianceRecord({
            eventType: eventType,
            isCompliant: isCompliant,
            timestamp: block.timestamp,
            verifiedBy: msg.sender
        });

        recordedEvents.push(eventHash);

        emit ComplianceRecorded(eventHash, eventType, isCompliant, msg.sender, block.timestamp);
    }

    function getComplianceStatus(bytes32 eventHash)
        external
        view
        returns (string memory eventType, bool isCompliant, uint256 timestamp, address verifiedBy)
    {
        ComplianceRecord memory rec = records[eventHash];
        return (rec.eventType, rec.isCompliant, rec.timestamp, rec.verifiedBy);
    }

    function getAllEvents() external view returns (bytes32[] memory) {
        return recordedEvents;
    }

    function attachFile(bytes32 eventHash, string memory cid, bytes32 dataKey) public {
        eventFiles[eventHash].push(cid);
        cidDataKeys[cid] = dataKey;
    }

    function getFiles(bytes32 eventHash) public view returns (string[] memory) {
        return eventFiles[eventHash];
    }

    function getDataKey(string memory cid) public view returns (bytes32) {
        return cidDataKeys[cid];
    }
}