# Narrow secret-scan false-positive record

**Date:** 31 October 2026  
**Repository:** AITECHPRODUCTS/Project1  
**Affected historic commit:** d4d095ee13e576ee33747a0f64ae9b4a78237260

Gitleaks reported its generic-api-key rule on a test-only SQLAlchemy fixture assignment in tests/test_affiliate_research_search.py, line 83, in the historic commit above. The matched literal was a synthetic placeholder string used as fake ciphertext in a SQLite integration test. It was not a provider credential, had never been accepted by any provider, and was not used outside that test.

The source fixture has been changed to one-character sentinels so the current tree no longer contains a realistic-looking dummy value. Because the repository's secret scan traverses all 619+ commits and the original commit cannot be safely rewritten under the no-history-rewrite constraint, .gitleaksignore contains only the exact Gitleaks fingerprint for that one historical line.

This is not a rule-wide, file-wide or path-wide exclusion. The pinned Gitleaks full-history scan remains enabled and all other findings remain blocking. Remove the single fingerprint entry only if the history is safely rewritten under a separately approved history-maintenance procedure. Do not add broad allowlists for real secrets.
