# Model artifact preparation and runtime policy

## Runtime contract

OmniAffiliateOS must not download Hugging Face model files as an implicit side effect of an API request, worker restart, or RAG ingestion. Embedding and local-transformer loaders run in **local-files-only** mode. A missing or incomplete cache/model directory is an error to resolve operationally, not permission to enable runtime network downloads.

For production Hub-based embedding models, set `EMBEDDING_MODEL` to the exact Hub repository ID and `EMBEDDING_MODEL_REVISION` to the immutable 40-character commit SHA reviewed for that repository. Stage the approved snapshot in the model cache/container/image before deploying the exact application SHA. Local directory models can be selected by an absolute mounted directory path.

Runtime uses `trust_remote_code=False`; do not enable it merely to load an unreviewed checkpoint. Local causal models and LoRA adapters must already exist on disk.

## Controlled preparation procedure

1. Obtain a model only through an operator-controlled build/release job with reviewed source, license and fixed revision. Do not fetch models from application runtime, a user-supplied path, or an API request.
2. Record the model repository, immutable commit SHA, license, artifact/cache digest, acquisition time, approving operator and the artifact/image containing the model.
3. Scan/license-review the model artifact as required by the deployment's supply-chain policy and distribute it through the approved artifact channel.
4. Set `EMBEDDING_MODEL_REVISION` in production and verify a cache-only load before promoting the image. The exact revision is part of the vector-index identity; changing revision requires re-ingestion into a new or empty index before cutover.
5. Run `python -m ai_memory.ingester --embedding-model "$EMBEDDING_MODEL" --embedding-revision "$EMBEDDING_MODEL_REVISION"` only after the artifact is staged. The command is local-files-only and fails clearly on a cache miss.
6. Preserve the previous model/index until retrieval golden tests and provenance checks pass; record model/index metadata and rollback target.

## Release evidence

CI tests the local-only policy and immutable revision validation. Those tests do not prove a real production model artifact has been staged, reviewed for licensing, benchmarked, or loaded against the deployed RAG index. Track those as deployment evidence. Never describe a model as downloaded/verified from CI if only imports and mocked unit tests ran.


## Release manifest gate (run on the staged deployment artifact)

Use an operator-controlled manifest to connect one application commit to exact staged model files, upstream revision, acquisition evidence and license approval. Do not check in a manifest claiming a model was approved unless the artifact was actually acquired and reviewed.

The UTF-8 JSON manifest requires schema_version 1, exact 40-character application_sha, and a non-empty artifacts array. Each artifact entry must include:
- name, kind (embedding, causal_lm or lora_adapter), source (huggingface_hub or operator_local), model_id, and a relative path beneath the artifact root.
- artifact_sha256 equal to the verifier's deterministic SHA-256 directory-tree digest. Stage materialized files rather than symlinks.
- For Hub sources, an immutable 40-character revision SHA. Mutable tags such as main and latest are rejected.
- license_id, license_review_status approved, license_reviewed_by, timezone-aware license_reviewed_at, acquired_by, and timezone-aware acquired_at.
- local_files_only true and trust_remote_code false.

Run after staged files and manifest arrive through the approved artifact channel and before image promotion:

    python scripts/verify_model_artifact_manifest.py --manifest /release/model-artifact-manifest.json --artifact-root /opt/omni/models --application-sha "$APPLICATION_GIT_SHA" --report-out /release/model-artifact-verification.json

A non-zero exit code blocks promotion. Archive the generated JSON report with the exact application SHA and deployment candidate. The verifier checks digest and metadata but does not cryptographically sign the manifest or prove a human's license approval is genuine; release owners must enforce those controls. CI uses temporary fixture artifacts only. No production model artifact is claimed staged or approved by those tests.
