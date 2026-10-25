from __future__ import annotations

from scripts.verify_chroma_security_boundary import verify_chroma_boundary


def test_chroma_remains_local_persistent_and_not_network_exposed():
    errors = verify_chroma_boundary()
    assert errors == [], "\\n".join(errors)
