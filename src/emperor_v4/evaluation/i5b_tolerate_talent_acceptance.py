"""Compatibility imports for the former tolerate-talent-specific module."""

from emperor_v4.evaluation.i5b_formal_fact_acceptance import (
    SCHEMA_VERSION,
    build_formal_fact_acceptance,
    main,
)

__all__ = ["SCHEMA_VERSION", "build_formal_fact_acceptance", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
