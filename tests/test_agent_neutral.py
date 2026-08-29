"""CR-001: pcbkit must not privilege any one agent.

See docs/sdlc/CR-001-agent-neutral/spec.md for the four-part definition these
tests enforce, and AGENTS.md rule 7 for the rule itself.

The point of running these from the start is that the constraint stays nearly
free. Retrofitting it after the knowledge layer and its evals are written
against one agent's shape is a rewrite.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from pcbkit.cli import build_parser

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "pcbkit"

VENDOR = re.compile(
    r"\b(claude|anthropic|codex|cursor|copilot|openai|gemini)\b", re.IGNORECASE
)

# The only environment variable pcbkit reads. Anything else risks coupling the
# toolkit to one harness's ambient state.
ALLOWED_ENV_VARS = {"PCBKIT_PCBNEW_PYTHON", "LC_ALL"}

# Capabilities that ship today. Each must be reachable from the CLI alone: a
# feature living only behind a hook or skill does not exist for other agents.
# Add to this as milestones land -- that is the point of the list.
SHIPPED_VERBS = {"doctor", "build"}


def python_sources() -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)


def test_there_are_sources_to_check():
    """Guard against the scan silently passing because it found nothing."""
    assert len(python_sources()) >= 8


@pytest.mark.parametrize("path", python_sources(), ids=lambda p: p.name)
def test_no_vendor_identifiers_in_the_package(path: Path):
    """Definition 1. Comments and docstrings count -- they steer the next agent."""
    hits = [
        f"{path.relative_to(REPO)}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text().splitlines(), start=1)
        if VENDOR.search(line)
    ]
    assert not hits, "vendor identifiers found:\n" + "\n".join(hits)


def test_every_shipped_capability_has_a_cli_verb():
    """Definition 2. The CLI is the portable surface; nothing may bypass it."""
    parser = build_parser()
    actions = [
        a for a in parser._subparsers._group_actions if hasattr(a, "choices")
    ]
    verbs = set(actions[0].choices)
    missing = SHIPPED_VERBS - verbs
    assert not missing, f"capabilities with no CLI verb: {sorted(missing)}"


def test_core_reads_no_agent_environment_variables():
    """Definition 3. Ambient harness state must not change pcbkit's behaviour."""
    def reads_env(func: ast.expr) -> bool:
        """True only for os.environ.get(...) and os.getenv(...).

        Matching a bare `.get` would flag every dict lookup in the package.
        """
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr == "getenv":
            return getattr(func.value, "id", None) == "os"
        if func.attr == "get":
            return getattr(func.value, "attr", None) == "environ"
        return False

    offenders: list[str] = []
    for path in python_sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and reads_env(node.func) and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if first.value not in ALLOWED_ENV_VARS:
                        offenders.append(
                            f"{path.relative_to(REPO)}:{node.lineno}: {first.value}"
                        )
            # os.environ["X"]
            if isinstance(node, ast.Subscript):
                if getattr(node.value, "attr", None) == "environ":
                    key = node.slice
                    if isinstance(key, ast.Constant) and key.value not in ALLOWED_ENV_VARS:
                        offenders.append(
                            f"{path.relative_to(REPO)}:{node.lineno}: {key.value}"
                        )
    assert not offenders, "unexpected environment variables:\n" + "\n".join(offenders)


def test_conventions_file_is_provider_neutral():
    """AGENTS.md is canonical; CLAUDE.md may exist only as a pointer to it."""
    agents = REPO / "AGENTS.md"
    assert agents.exists(), "AGENTS.md is the canonical conventions file"
    assert "No agent may be privileged" in agents.read_text()

    pointer = REPO / "CLAUDE.md"
    if pointer.exists():
        text = pointer.read_text()
        assert "AGENTS.md" in text
        assert len(text.splitlines()) < 15, (
            "CLAUDE.md must stay a pointer; conventions belong in AGENTS.md"
        )


def test_generated_agent_adapters_are_in_sync():
    """Definition 4. Inert until the M7 source of truth exists, then automatic."""
    source = REPO / "docs" / "agent" / "workflow.md"
    if not source.exists():
        pytest.skip("docs/agent/workflow.md arrives with M7")

    adapters = [REPO / "skills" / "pcb-design" / "SKILL.md"]
    present = [a for a in adapters if a.exists()]
    assert present, "workflow.md exists but no adapter was generated from it"
    for adapter in present:
        assert source.name in adapter.read_text(), (
            f"{adapter.relative_to(REPO)} must declare its generated source"
        )
