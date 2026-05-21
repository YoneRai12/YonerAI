from src.cogs import mcp_policy


def test_mcp_tool_runtime_policy_denies_dangerous_names_by_default():
    patterns = ["delete", "deploy", "shell", "run"]

    assert mcp_policy.is_mcp_tool_denied("delete_file", patterns)
    assert mcp_policy.is_mcp_tool_denied("deploy_release", patterns)
    assert mcp_policy.is_mcp_tool_denied("run_shell", patterns)
    assert not mcp_policy.is_mcp_tool_denied("generate_artwork", patterns)


def test_mcp_tool_runtime_policy_allows_dangerous_only_when_explicit():
    patterns = ["delete"]

    assert mcp_policy.is_mcp_tool_denied("delete_file", patterns)
    assert not mcp_policy.is_mcp_tool_denied("delete_file", patterns, allow_dangerous=True)


def test_mcp_deny_pattern_env_override_is_normalized(monkeypatch):
    monkeypatch.setenv("ORA_MCP_DENY_TOOL_PATTERNS", " Purge , Launch ")

    patterns = mcp_policy.load_mcp_deny_patterns()

    assert patterns == ["purge", "launch"]
    assert mcp_policy.is_mcp_tool_denied("safe_purge_cache", patterns)
    assert mcp_policy.is_mcp_tool_denied("launch_process", patterns)
    assert not mcp_policy.is_mcp_tool_denied("list_resources", patterns)
