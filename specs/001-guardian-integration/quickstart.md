# Quickstart: Guardian Integration (local dev)

**Feature**: `001-guardian-integration` | **Date**: 2026-04-20

Adapted from [docs/guardian-integration/01-setup.md](../../docs/guardian-integration/01-setup.md) and [docs/guardian-integration/03-gps-submission.md](../../docs/guardian-integration/03-gps-submission.md). This is the minimum set of steps to boot a working Guardian integration on your machine and run the acceptance tests.

Prereqs:

- Python 3.11 and `uv` (already used by Spec Kit).
- Access to an MGS testnet tenant (or a fresh account to provision one — see §1).
- Repo bootstrapped: `api/` venv, `pytest` runnable.

---

## 1. Provision MGS testnet tenant (one-time, external)

In the MGS portal:

1. Create an MGS account and accept the Terms of Service. Before ToS is accepted, the API returns `451` for every call.
2. Provision the tenant: `PUT /tenants/user`.
3. Register the Standard Registry: `POST /accounts/register` with `role: STANDARD_REGISTRY`.
4. Set Hedera credentials (activates the SR DID): `PUT /profiles/{sr-username}`.
5. Capture:
   - `GUARDIAN_API_URL` = `https://guardianservice.app/api/v1`
   - `GUARDIAN_SR_USERNAME`, `GUARDIAN_SR_PASSWORD`
   - SR DID (visible via `GET /profiles/{sr-username}`)

Write these into the `testnet` secret store; do not commit.

## 2. Configure the FastAPI app

Edit `api/app/core/config.py` (or the `.env` layered on top, per existing convention):

```
GUARDIAN_NETWORK=testnet
GUARDIAN_API_URL=https://guardianservice.app/api/v1
GUARDIAN_SR_USERNAME=<sr-username>
GUARDIAN_SR_PASSWORD=<sr-password>
GUARDIAN_GDST_POLICY_ID=               # filled in after step 4
GUARDIAN_FSMA_POLICY_ID=               # filled in after step 4
GUARDIAN_GDST_INTAKE_BLOCK_TAG=        # filled in after step 4
GUARDIAN_FSMA_INTAKE_BLOCK_TAG=        # filled in after step 4
```

## 3. Publish schemas

Run the one-time bootstrap script (to be produced by `/speckit-implement`). Pseudocode:

```python
for schema_file in glob("schemas/gdst/*.json") + glob("schemas/fsma/*.json"):
    schema = guardian_client.create_schema(json.load(open(schema_file)))       # POST /schemas (sync)
    task = guardian_client.publish_schema(schema["id"])                         # PUT /schemas/push/{id}/publish (async)
    guardian_client.wait_for_task(task["taskId"])                               # GET /tasks/{taskId}
```

## 4. Create and publish policies, then export

```python
gdst_policy = guardian_client.create_policy({ ... GDST policy definition ... })
task = guardian_client.publish_policy(gdst_policy["id"])                         # PUT /policies/push/{id}/publish
guardian_client.wait_for_task(task["taskId"])
guardian_client.export_policy(gdst_policy["id"], "schemas/policies/gdst-seafood-traceability.policy")

fsma_policy = guardian_client.create_policy({ ... FSMA policy definition ... })
task = guardian_client.publish_policy(fsma_policy["id"])
guardian_client.wait_for_task(task["taskId"])
guardian_client.export_policy(fsma_policy["id"], "schemas/policies/fsma-204-food-safety.policy")
```

Record `GUARDIAN_GDST_POLICY_ID`, `GUARDIAN_FSMA_POLICY_ID`, and the intake block tags in the env.

## 5. Pre-provision operators (out-of-band — v1)

Operator onboarding is **out of scope for v1**. Provision each operator directly in the MGS portal before running any event flow:

1. Log into the MGS portal as the SR.
2. Create a `User` account per operator, set their Hedera credentials to activate the DID, and record the resulting `did:hedera:testnet:...` in your deployment-runbook operator registry.
3. Capture signed consent for the FR-015 full-payload VC disclosure posture before issuing any event on behalf of that operator. Retain the signed record locally (e.g., a counter-signed PDF or an entry in a secured consent log). v1 does not ship an in-product consent prompt.

v2 will add FastAPI endpoints for operator self-service registration (`POST /guardian/register`) and DID resolution (`GET /guardian/did/{username}`); until then, these endpoints do not exist and the `guardian_client` has no onboarding methods.

## 6. Submit a sample event end-to-end

```bash
# Sample assumes you've started the FastAPI app.
curl -X POST http://localhost:8000/events/gdst/fishing \
  -H "Authorization: Bearer <operator-jwt>" \
  -H "Content-Type: application/json" \
  --data-binary @samples/gdst/fishing.json
```

Then fetch the VC:

```bash
curl http://localhost:8000/guardian/gdst/vc/<event-hash>
```

Expected: a `GDSTComplianceCredential` whose `credentialSubject.eventHash` equals the on-chain event hash and whose `complianceStatus` is `compliant`.

## 7. Run the acceptance tests

```bash
cd api
pytest app/tests/integration/guardian -v
```

All rules in [data-model.md §Rule Source Table](data-model.md) must pass. A recorded-response fixture is used by default; set `GUARDIAN_LIVE=1` to hit a real MGS tenant.

## 8. Health checks

```bash
curl http://localhost:8000/guardian/health
```

Expected body: `{ "status": "ok", "breaker": "closed", "sr_did": "did:hedera:testnet:..." }`.

Other possible `status` values: `tos_required` (MGS `451`), `breaker_open`, `unavailable`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| All calls return `451` | MGS ToS not accepted on the tenant | Log in to the MGS portal and accept. `/guardian/health` reports `tos_required`. |
| VC lookup returns 404 for a compliant event | Async task still running on Guardian | Wait and retry; confirm via `GET /tasks/{taskId}` from the submission log. |
| `/events/*` latency spikes when MGS is slow | Submission is not truly async or breaker not opening | Check `guardian_client.circuit_status()`. Verify the Guardian submit call is scheduled after HCS and does not block the response. |
| Schema publish times out | MGS task pipeline backlog | `wait_for_task` caps at 120 s; re-run the bootstrap step — `create_schema` is idempotent by name. |
