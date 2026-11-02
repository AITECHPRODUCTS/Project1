# Skill feedback and evaluation protocol

Record failure as structured evidence: skill ID, version, attempted stage, expected contract, actual result, provider status, sanitized error, retry count, and whether human intervention was required.

Classify failure as missing input, unsupported capability, authorization denied, provider contract changed, rate-limited, timeout, schema mismatch, incorrect output, ungrounded claim, or policy violation. Never log secrets, session tokens, full personal data, or private provider responses.

A skill is only upgraded from partial/not implemented after tests prove its input/output contract, authorization behavior, failure path, idempotency, persistence and user-facing status. Test runs and source availability are not proof that production workflows work. Preserve failed evaluation examples and rerun them after fixes.
