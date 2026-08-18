import logging
from typing import Any

from jsonschema import ValidationError, validate


logger = logging.getLogger(__name__)


def validate_generated_json(
    instance: Any,
    schema: dict[str, Any],
    *,
    kind: str,
) -> None:
    """Validate provider JSON without copying provider content into exceptions or logs."""
    try:
        validate(instance=instance, schema=schema)
    except ValidationError:
        logger.warning("generated_json_schema_validation_failed kind=%s", kind)
        raise ValueError(f"{kind} model returned an invalid schema") from None
