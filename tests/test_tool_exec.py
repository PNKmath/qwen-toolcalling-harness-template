from harness.tools import exec_tool


def test_add_numbers():
    out = exec_tool("add_numbers", '{"a": 1, "b": 2}')
    assert '"result": 3' in out


def test_unknown_tool():
    out = exec_tool("unknown", '{}')
    assert "unknown tool" in out


def test_invalid_json():
    out = exec_tool("add_numbers", '{bad json}')
    assert "invalid tool args json" in out
