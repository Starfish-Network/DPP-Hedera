# Cost Report

## Overview
This document provides a high-level cost report for an application that performs transactions on the **Hedera Hashgraph** network.

---

## Network
- **Blockchain:** Hedera Hashgraph (Public Mainnet)
- **Consensus:** Hashgraph (aBFT)
- **Services Used:**
  - Hedera Consensus Service (HCS)
  - Hedera Smart Contract Service (EVM)

---

## Cost Model Summary
Hedera uses **fixed, USD-pegged fees** that are not subject to gas price volatility.

| Category | Cost Characteristic |
|-------|---------------------|
| Transaction Fees | Low, predictable, USD-based |
| Contract Execution | Deterministic and capped |

---

## Transaction Costs (Current)

| Operation | Current Cost (HBAR) | Current Cost (USD) |
|---------|--------------------|-----------------|
| HCS Message Submit | 74.146HBAR | ~$0.0001 |
| Contract Deployment | 4.302HBAR | ~$0.5 – $1 |
| Contract Call | 0.104HBAR | ~nothing |

> Actual fees depend on payload size, contract complexity, and network configuration.

---

## Key Cost Drivers
- Transaction volume
- Smart contract complexity
- Payload size (HCS messages)

---

## Cost Stability & Advantages
- No gas price spikes
- Use of mirror nodes instead of public nodes
- Low fees enable high-throughput use cases

---

## Risks & Notes
- Fees subject to Hedera governance updates (USD pricing maintained)
- Smart contract inefficiencies increase execution cost

This document serves as a **cost reference** and should be updated if transaction patterns or Hedera services used change.
