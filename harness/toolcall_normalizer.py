# qwen3_coder fallback format:
#   <tool_call><function=name><parameter=key>value</parameter></function></tool_call>
# normalize_tool_calls_from_message() returns:
#   {"tool_calls": [{"id", "name", "arguments"}], "clean_content": str|None, "source": standard|fallback|none}

import ast
import json
import re
import uuid
from typing import Any, Dict, List, Optional, TypedDict


class ToolCallNormalized(TypedDict):
    id: str
    name: str
    arguments: str  # JSON string passed directly to exec_tool


class NormalizeResult(TypedDict):
    tool_calls: List[ToolCallNormalized]
    clean_content: Optional[str]
    source: str  # "standard" | "fallback" | "none"


def _try_convert_value(value: str) -> Any:
    # JSON → ast.literal_eval → string
    stripped = value.strip()

    if stripped.lower() == "null":
        return None

    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError, TypeError):
        pass

    return stripped


_TOOL_CALL_RE = re.compile(
    r"<tool_call>(.*?)</tool_call>|<tool_call>(.*?)$",
    re.DOTALL,
)

_FUNCTION_RE = re.compile(
    r"<function=(.*?)</function>|<function=(.*)$",
    re.DOTALL,
)

_PARAMETER_RE = re.compile(
    r"<parameter=(.*?)(?:</parameter>|(?=<parameter=)|(?=</function>)|$)",
    re.DOTALL,
)


def _parse_function_block(function_str: str) -> Optional[ToolCallNormalized]:
    try:
        if ">" not in function_str:
            return None

        gt_idx = function_str.index(">")
        func_name = function_str[:gt_idx].strip()
        params_str = function_str[gt_idx + 1:]

        param_dict: Dict[str, Any] = {}
        for match_text in _PARAMETER_RE.findall(params_str):
            if ">" not in match_text:
                continue
            eq_idx = match_text.index(">")
            param_name = match_text[:eq_idx].strip()
            param_value = match_text[eq_idx + 1:]

            # strip formatting artifacts from tag body
            if param_value.startswith("\n"):
                param_value = param_value[1:]
            if param_value.endswith("\n"):
                param_value = param_value[:-1]

            param_dict[param_name] = _try_convert_value(param_value)

        return ToolCallNormalized(
            id=f"fallback-{uuid.uuid4().hex}",
            name=func_name,
            arguments=json.dumps(param_dict, ensure_ascii=False),
        )
    except (ValueError, IndexError):
        return None


def extract_fallback_tool_calls(content: str) -> List[ToolCallNormalized]:
    if "<function=" not in content:
        return []

    try:
        tc_matches = _TOOL_CALL_RE.findall(content)
        raw_blocks = [m[0] if m[0] else m[1] for m in tc_matches]

        # If no <tool_call> wrappers found, attempt the whole string
        if not raw_blocks:
            raw_blocks = [content]  # no wrapper tags — try whole string

        function_strs: List[str] = []
        for block in raw_blocks:
            func_matches = _FUNCTION_RE.findall(block)
            function_strs.extend(m[0] if m[0] else m[1] for m in func_matches)

        if not function_strs:
            return []

        result: List[ToolCallNormalized] = []
        for func_str in function_strs:
            parsed = _parse_function_block(func_str)
            if parsed is not None:
                result.append(parsed)

        return result
    except Exception:
        return []


def normalize_tool_calls_from_message(msg: Any) -> NormalizeResult:
    try:
        def _get(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        standard_tcs = _get(msg, "tool_calls")
        if standard_tcs:
            normalized: List[ToolCallNormalized] = []
            for tc in standard_tcs:
                tc_id = _get(tc, "id") or f"fallback-{uuid.uuid4().hex}"
                fn = _get(tc, "function")
                if fn is None:
                    continue
                name = _get(fn, "name") or ""
                arguments = _get(fn, "arguments") or "{}"
                # arguments must be a JSON string for exec_tool
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments, ensure_ascii=False)
                normalized.append(ToolCallNormalized(id=tc_id, name=name, arguments=arguments))

            raw_content = _get(msg, "content") or ""
            first_tc = raw_content.find("<tool_call>") if raw_content else -1
            clean_content: Optional[str] = None
            if first_tc > 0:
                clean_content = raw_content[:first_tc].strip() or None

            return NormalizeResult(
                tool_calls=normalized,
                clean_content=clean_content,
                source="standard",
            )

        content = _get(msg, "content") or ""
        if not isinstance(content, str):
            content = str(content)

        fallback_tcs = extract_fallback_tool_calls(content)

        if fallback_tcs:
            first_tc_pos = content.find("<tool_call>")
            if first_tc_pos < 0:
                first_tc_pos = content.find("<function=")
            if first_tc_pos > 0:
                clean = content[:first_tc_pos].strip()
                clean_content = clean if clean else None
            else:
                clean_content = None

            return NormalizeResult(
                tool_calls=fallback_tcs,
                clean_content=clean_content,
                source="fallback",
            )

        return NormalizeResult(
            tool_calls=[],
            clean_content=None,
            source="none",
        )

    except Exception:
        return NormalizeResult(
            tool_calls=[],
            clean_content=None,
            source="none",
        )
