"""Keep reproducible source identifiers public while omitting workstation cache locations."""

from typing import Any


def public_source(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "cache_dir"}
