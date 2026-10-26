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
