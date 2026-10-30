from __future__ import annotations

from scripts.verify_vector_store_security_boundary import verify_vector_store_boundary


def test_vector_store_is_local_sqlite_and_does_not_install_or_import_chroma():
    errors = verify_vector_store_boundary()
    assert errors == [], "\\n".join(errors)
