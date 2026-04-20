"""
Pydantic ↔ Guardian JSON-LD mapper.

Builds `credentialSubject` objects for the two VC types declared in
specs/001-guardian-integration/contracts/vc-output.schema.json:

    to_credential_subject_gdst(event, policy_version, supersedes=None) -> dict
    to_credential_subject_fsma(event, policy_version, supersedes=None) -> dict

Both mappers embed the full event payload verbatim (FR-015) plus the
`GuaranteedMetadata` fields (eventHash, complianceStatus, policyVersion,
issuedAt, optional supersedes) and the type-specific discriminator
(`gdstEventType` / `fsma204EventType`).
"""
