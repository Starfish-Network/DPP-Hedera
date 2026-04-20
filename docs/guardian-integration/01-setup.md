# Setup: MGS Account, Identity, and API

We use **Managed Guardian Service (MGS)** as the Guardian runtime. MGS is a Hedera-managed multi-tenant Guardian instance — no Docker, no MongoDB, no IPFS, no Hedera operator to manage on our side.

OpenAPI reference: [api-docs-yaml](api-docs-yaml) (canonical source for endpoint paths and DTOs).

---

## 1. MGS Account Provisioning

One-time external setup, done in the MGS portal:

| Step | Action | Endpoint |
|------|--------|----------|
| 1 | Create MGS account, accept Terms of Service | (portal — `451` returned by API until ToS accepted) |
| 2 | Provision tenant | `PUT /tenants/user` |
| 3 | Register Standard Registry user | `POST /accounts/register` with `role: STANDARD_REGISTRY` |
| 4 | Set Hedera credentials → activates SR DID | `PUT /profiles/{username}` (or `/push/{username}` for async) |
| 5 | Capture base URL + SR credentials for our config | — |

> **TODO:** MGS tenant not yet provisioned. Replace `<mgs-tenant>` placeholder in the config block once available.

---

## 2. Configuration: `api/app/core/config.py`

```python
GUARDIAN_API_URL: str = "https://<mgs-tenant>.hedera.com/api/v1"  # provided by MGS
GUARDIAN_SR_USERNAME: str = ""
GUARDIAN_SR_PASSWORD: str = ""
```

---

## 3. REST Client: `api/app/service/guardian_client.py`

| Method | MGS API | Purpose |
|--------|---------|---------|
| `login()` | `POST /accounts/login` | Authenticate (returns JWT) |
| `get_health()` | `GET /accounts/session` | Validate session / health check |
| `register_user()` | `POST /accounts/register` | Create user under tenant |
| `get_user_did()` | `GET /profiles/{username}` | Resolve DID |
| `set_user_credentials()` | `PUT /profiles/{username}` | Activate user DID with Hedera credentials |
| `create_schema()` | `POST /schemas` | Create schema (SR only) |
| `publish_schema()` | `PUT /schemas/{id}/publish` | Publish schema (use `/push/` for async) |
| `create_policy()` | `POST /policies` | Create policy (SR only) |
| `publish_policy()` | `PUT /policies/{id}/publish` | Publish policy (use `/push/` for async) |
| `export_policy()` | `GET /policies/{id}/export/file` | Export `.policy` zip file |
| `submit_document()` | `POST /external/{policyId}/{blockTag}` | Submit event document to policy block |
| `get_vc()` | `GET /policies/{id}/documents?type=VC` | Query VCs (filter by `credentialSubject.eventHash`) |
| `get_task_status()` | `GET /tasks/{taskId}` | Poll status of async (`/push/`) operations |

**Async pattern.** Long-running operations (publish schema, publish policy, profile setup) have `/push/` variants that return a `TaskDTO` with a `taskId`. The client polls `get_task_status(taskId)` until completion. Sync endpoints are fine for fast operations (login, query documents).

**Circuit breaker.** After 3 consecutive failures, Guardian calls are skipped for 60 seconds. Core HCS/contract flows are unaffected.

---

## 4. Identity and DIDs

### Standard Registry (SR)

The SR is the root authority that owns policies and issues VCs. Registered once during MGS provisioning (Step 3 above). The SR's DID becomes the `issuer` on all VCs — this is the trust anchor.

### User Registration

| Existing Role | Guardian Role | Purpose |
|---------------|---------------|---------|
| `admin` | Standard Registry | Owns policies |
| `operator` | User | Submits events, receives VCs |

```
Operator registers → SR sets credentials → DID activated on Hedera
```

MGS activates the DID server-side once Hedera credentials are set via `PUT /profiles/{username}` — there is no separate "approve" call. Once active, the login JWT includes a `did` claim (resolved at login, cached in token).

---

## 5. API Endpoints

Base path: `/api/v1/guardian` — JWT auth required.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/guardian/health` | Any | Health check (proxies `GET /accounts/session`) |
| `POST` | `/guardian/register` | Any | Register user via MGS |
| `GET` | `/guardian/did/{username}` | Any | Resolve DID |
| `GET` | `/guardian/gdst/vc/{event_hash}` | Any | Retrieve GDST VC |
| `GET` | `/guardian/fsma/vc/{event_hash}` | Any | Retrieve FSMA VC |

Error codes: `404` (not found), `409` (username exists), `451` (MGS ToS not accepted), `503` (MGS unavailable).

---

## Files

```
api/app/core/config.py                  (MODIFIED — MGS settings)
api/app/service/guardian_client.py      (NEW)
api/app/routes/guardian/identity.py     (NEW)
api/app/core/auth.py                    (MODIFIED — DID in JWT)
api/app/main.py                         (MODIFIED — register guardian router)
```

## Verification

1. `GET /accounts/session` against the MGS base URL returns 200 with a valid JWT
2. Standard Registry user has a Hedera DID (visible via `GET /profiles/{sr-username}`)
3. A registered operator user has a Hedera DID after `PUT /profiles/{username}` completes
4. All existing tests still pass
