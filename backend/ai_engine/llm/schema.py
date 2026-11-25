"""Convert a Pydantic model into a JSON schema accepted by strict structured-output modes.

Strict modes (Claude structured outputs, OpenAI strict json_schema) want every object closed
(`additionalProperties: false`), every property listed in `required`, and no unsupported keywords.
Optional fields stay optional in meaning by being nullable, not by being absent.
"""

from typing import Any

from pydantic import BaseModel

_DROP = {"title", "default", "examples", "maxLength", "minLength", "maxItems", "minItems", "pattern", "format"}


def _resolve(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return _resolve(defs[name], defs)
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _DROP or key == "$defs":
                continue
            if key == "properties" and isinstance(value, dict):
                # Keys here are field names (a field may be called "title"), never schema keywords.
                out[key] = {name: _resolve(sub, defs) for name, sub in value.items()}
                continue
            out[key] = _resolve(value, defs)
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"].keys())
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return [_resolve(v, defs) for v in node]
    return node


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    return _resolve(raw, raw.get("$defs", {}))
