"""
Unit tests for harness.toolcall_normalizer.

Test cases:
  1. Standard tool_calls path (source="standard")
  2. Single <tool_call> tag fallback (source="fallback")
  3. Multiple <tool_call> blocks (2+)
  4. Broken / unparseable block → empty list
  5. no-tool (tool_calls=None, no tags in content) → source="none"
  6. Unclosed </tool_call> tag (EOF termination)
  7. Mixed: standard tool_calls present → fallback NOT executed
  8. clean_content extraction before first <tool_call>
  9. Value type conversion (int, float, bool, null, JSON object)
 10. extract_fallback_tool_calls directly (unit-level)
"""

import json

import pytest

from harness.toolcall_normalizer import (
    NormalizeResult,
    ToolCallNormalized,
    extract_fallback_tool_calls,
    normalize_tool_calls_from_message,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_std_tc(name: str, args: dict, tc_id: str = "call_abc123") -> dict:
    """Return a dict mimicking an OpenAI ChatCompletionMessageToolCall."""
    return {
        "id": tc_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _make_msg(tool_calls=None, content: str = "") -> dict:
    return {"role": "assistant", "content": content, "tool_calls": tool_calls}


SINGLE_TAG_CONTENT = """\
<tool_call>
<function=add_numbers>
<parameter=a>3</parameter>
<parameter=b>7</parameter>
</function>
</tool_call>"""

TWO_TAG_CONTENT = """\
<tool_call>
<function=get_weather>
<parameter=city>Seoul</parameter>
</function>
</tool_call>
<tool_call>
<function=add_numbers>
<parameter=a>1</parameter>
<parameter=b>2</parameter>
</function>
</tool_call>"""

UNCLOSED_TAG_CONTENT = """\
<tool_call>
<function=search_docs>
<parameter=query>tool calling</parameter>
</function>"""  # </tool_call> intentionally omitted

BROKEN_CONTENT = """\
<tool_call>
this is not a function block at all
</tool_call>"""

PREFIX_CONTENT = "Sure, let me add those numbers.\n" + SINGLE_TAG_CONTENT


# ---------------------------------------------------------------------------
# Test 1: Standard tool_calls path
# ---------------------------------------------------------------------------

def test_standard_path_source():
    tc = _make_std_tc("add_numbers", {"a": 1, "b": 2})
    msg = _make_msg(tool_calls=[tc])
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "standard"


def test_standard_path_tool_call_fields():
    tc = _make_std_tc("add_numbers", {"a": 1, "b": 2}, tc_id="call_xyz")
    msg = _make_msg(tool_calls=[tc])
    result = normalize_tool_calls_from_message(msg)
    assert len(result["tool_calls"]) == 1
    normalized = result["tool_calls"][0]
    assert normalized["id"] == "call_xyz"
    assert normalized["name"] == "add_numbers"
    args = json.loads(normalized["arguments"])
    assert args == {"a": 1, "b": 2}


def test_standard_path_clean_content_none_when_no_prefix():
    tc = _make_std_tc("add_numbers", {"a": 5, "b": 5})
    msg = _make_msg(tool_calls=[tc], content="")
    result = normalize_tool_calls_from_message(msg)
    assert result["clean_content"] is None


# ---------------------------------------------------------------------------
# Test 2: Single <tool_call> tag fallback
# ---------------------------------------------------------------------------

def test_single_tag_fallback_source():
    msg = _make_msg(content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "fallback"


def test_single_tag_fallback_fields():
    msg = _make_msg(content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert len(result["tool_calls"]) == 1
    tc = result["tool_calls"][0]
    assert tc["name"] == "add_numbers"
    args = json.loads(tc["arguments"])
    assert args["a"] == 3
    assert args["b"] == 7
    assert tc["id"].startswith("fallback-")


def test_single_tag_fallback_clean_content_none():
    msg = _make_msg(content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["clean_content"] is None


# ---------------------------------------------------------------------------
# Test 3: Multiple <tool_call> blocks
# ---------------------------------------------------------------------------

def test_multiple_tag_blocks_count():
    msg = _make_msg(content=TWO_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "fallback"
    assert len(result["tool_calls"]) == 2


def test_multiple_tag_blocks_order():
    msg = _make_msg(content=TWO_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    names = [tc["name"] for tc in result["tool_calls"]]
    assert names == ["get_weather", "add_numbers"]


def test_multiple_tag_blocks_args():
    msg = _make_msg(content=TWO_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    weather_args = json.loads(result["tool_calls"][0]["arguments"])
    add_args = json.loads(result["tool_calls"][1]["arguments"])
    assert weather_args == {"city": "Seoul"}
    assert add_args == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# Test 4: Broken/unparseable block → empty list
# ---------------------------------------------------------------------------

def test_broken_block_empty_tool_calls():
    msg = _make_msg(content=BROKEN_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["tool_calls"] == []


def test_broken_block_source_none():
    msg = _make_msg(content=BROKEN_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "none"


def test_no_function_tag_in_content():
    msg = _make_msg(content="Hello world, no tools here.")
    result = normalize_tool_calls_from_message(msg)
    assert result["tool_calls"] == []
    assert result["source"] == "none"


# ---------------------------------------------------------------------------
# Test 5: no-tool (tool_calls=None, content has no tags) → source="none"
# ---------------------------------------------------------------------------

def test_no_tool_source():
    msg = _make_msg(tool_calls=None, content="The answer is 42.")
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "none"


def test_no_tool_empty_list():
    msg = _make_msg(tool_calls=None, content="The answer is 42.")
    result = normalize_tool_calls_from_message(msg)
    assert result["tool_calls"] == []


def test_no_tool_clean_content_none():
    msg = _make_msg(tool_calls=None, content="The answer is 42.")
    result = normalize_tool_calls_from_message(msg)
    assert result["clean_content"] is None


# ---------------------------------------------------------------------------
# Test 6: Unclosed </tool_call> tag (EOF termination)
# ---------------------------------------------------------------------------

def test_unclosed_tool_call_tag_parsed():
    msg = _make_msg(content=UNCLOSED_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "fallback"
    assert len(result["tool_calls"]) == 1
    tc = result["tool_calls"][0]
    assert tc["name"] == "search_docs"
    args = json.loads(tc["arguments"])
    assert args["query"] == "tool calling"


# ---------------------------------------------------------------------------
# Test 7: Standard tool_calls present → fallback NOT executed
# ---------------------------------------------------------------------------

def test_standard_beats_fallback():
    """When message.tool_calls is present, fallback tag parsing is skipped."""
    tc = _make_std_tc("add_numbers", {"a": 10, "b": 20})
    # content also contains a tag block — should be ignored
    msg = _make_msg(tool_calls=[tc], content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "standard"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "add_numbers"
    args = json.loads(result["tool_calls"][0]["arguments"])
    assert args == {"a": 10, "b": 20}


# ---------------------------------------------------------------------------
# Test 8: clean_content extracted from text before first <tool_call>
# ---------------------------------------------------------------------------

def test_clean_content_extracted():
    msg = _make_msg(content=PREFIX_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["clean_content"] == "Sure, let me add those numbers."


def test_clean_content_none_when_tag_at_start():
    msg = _make_msg(content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    assert result["clean_content"] is None


# ---------------------------------------------------------------------------
# Test 9: Value type conversion (int, float, bool, null, JSON object)
# ---------------------------------------------------------------------------

def test_value_type_int():
    content = "<tool_call>\n<function=add_numbers>\n<parameter=a>42</parameter>\n<parameter=b>0</parameter>\n</function>\n</tool_call>"
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert args["a"] == 42
    assert isinstance(args["a"], int)


def test_value_type_float():
    content = "<tool_call>\n<function=add_numbers>\n<parameter=a>3.14</parameter>\n<parameter=b>0.0</parameter>\n</function>\n</tool_call>"
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert abs(args["a"] - 3.14) < 1e-9


def test_value_type_bool_true():
    content = '<tool_call>\n<function=add_numbers>\n<parameter=flag>true</parameter>\n</function>\n</tool_call>'
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert args["flag"] is True


def test_value_type_null():
    content = '<tool_call>\n<function=add_numbers>\n<parameter=val>null</parameter>\n</function>\n</tool_call>'
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert args["val"] is None


def test_value_type_json_object():
    content = '<tool_call>\n<function=search_docs>\n<parameter=opts>{"k": 5}</parameter>\n</function>\n</tool_call>'
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert args["opts"] == {"k": 5}


def test_value_type_string_fallback():
    content = '<tool_call>\n<function=get_weather>\n<parameter=city>Seoul</parameter>\n</function>\n</tool_call>'
    tcs = extract_fallback_tool_calls(content)
    args = json.loads(tcs[0]["arguments"])
    assert args["city"] == "Seoul"
    assert isinstance(args["city"], str)


# ---------------------------------------------------------------------------
# Test 10: extract_fallback_tool_calls direct unit tests
# ---------------------------------------------------------------------------

def test_extract_returns_empty_for_no_function_tag():
    result = extract_fallback_tool_calls("Just some regular text.")
    assert result == []


def test_extract_multiple_blocks_directly():
    result = extract_fallback_tool_calls(TWO_TAG_CONTENT)
    assert len(result) == 2


def test_extract_unclosed_tag_directly():
    result = extract_fallback_tool_calls(UNCLOSED_TAG_CONTENT)
    assert len(result) == 1
    assert result[0]["name"] == "search_docs"


# ---------------------------------------------------------------------------
# Test 11: arguments is always a valid JSON string
# ---------------------------------------------------------------------------

def test_arguments_is_json_string_standard():
    tc = _make_std_tc("add_numbers", {"a": 1, "b": 2})
    msg = _make_msg(tool_calls=[tc])
    result = normalize_tool_calls_from_message(msg)
    for item in result["tool_calls"]:
        parsed = json.loads(item["arguments"])
        assert isinstance(parsed, dict)


def test_arguments_is_json_string_fallback():
    msg = _make_msg(content=SINGLE_TAG_CONTENT)
    result = normalize_tool_calls_from_message(msg)
    for item in result["tool_calls"]:
        parsed = json.loads(item["arguments"])
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Test 12: Object-style message (attribute access, not dict)
# ---------------------------------------------------------------------------

class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, tc_id, fn):
        self.id = tc_id
        self.function = fn


class _FakeMsg:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls
        self.content = content


def test_object_style_standard_message():
    fn = _FakeFunction("add_numbers", '{"a": 5, "b": 5}')
    tc = _FakeToolCall("call_obj1", fn)
    msg = _FakeMsg(tool_calls=[tc], content="")
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "standard"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "add_numbers"


def test_object_style_no_tool():
    msg = _FakeMsg(tool_calls=None, content="Hello!")
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "none"
    assert result["tool_calls"] == []
