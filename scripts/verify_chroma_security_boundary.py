"""Compatibility entry point for the retired Chroma-only guard name."""

from scripts.verify_vector_store_security_boundary import main

if __name__ == "__main__":
    raise SystemExit(main())
