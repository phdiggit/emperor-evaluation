from __future__ import annotations


class HumanReadableMarkdownValidationError(RuntimeError):
    def __init__(self, errors: list[str]):
        super().__init__("human-readable split markdown export validation failed")
        self.errors = errors
