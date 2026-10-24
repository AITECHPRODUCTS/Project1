# AI, RAG and proprietary model strategy

## RAG first
Ingest licensed reference doctrine, preserve source path/heading/hash, pin embedding model and dimensionality, retrieve before generation, show evidence provenance, test gold queries/recall, evaluate claim grounding and defend against prompt injection, poisoned sources and stale records. Retrieved material is untrusted reference and cannot override system policy or authorization.

## Model modes
- `offline`: deterministic development drafts only, never labeled as model-generated.
- OpenAI-compatible: server-side API secret, pinned model, cost/timeouts/retries and sanitized logs.
- Local Transformers: operator-supplied model path/device with optional LoRA adapter; CPU/GPU capability and VRAM must be validated.
- Fine-tuning: separate pipeline for licensed/consented datasets, splits, deduplication, PII checks, quality baselines, held-out evaluation, artifact hashes, promotion review and rollback.

## Learning
RAG evidence, performance memory, feedback evaluation and weight fine-tuning are separate data planes. Only adequately sampled, confirmed events become hypotheses; reversals, source expiry and drift must invalidate stale learning. Current branch loads a local adapter and has RAG/performance-memory scaffolding, but the full governed training/promote/rollback pipeline remains incomplete.
