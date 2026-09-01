"""Every wiki/tools/*.md page must carry a valid `phase:` and a `## Core usage`
fenced command. The offensive-driver tool-index builder reads exactly these two."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL_PAGES = sorted((ROOT / "wiki" / "tools").glob("*.md"))
ALLOWED_PHASES = {"recon", "enumerate", "exploit", "postex"}


def _phase(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    pm = re.search(r"^phase:\s*(\S+)\s*$", m.group(1), re.MULTILINE)
    return pm.group(1) if pm else None


def _core_usage_first_line(text):
    """First runnable line inside the fenced block under `## Core usage`.
    Returns the line, or None if the section / fence / command is missing."""
    m = re.search(r"^##\s+Core usage\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    fence = re.search(r"```[^\n]*\n(.*?)```", m.group(1), re.DOTALL)
    if not fence:
        return None
    for raw in fence.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):   # skip blanks and comments
            continue
        return line
    return None


def test_every_tool_page_has_phase_and_usage():
    assert TOOL_PAGES, "no tool pages found under wiki/tools/"
    offenders = []
    for page in TOOL_PAGES:
        text = page.read_text(encoding="utf-8")
        phase = _phase(text)
        if phase not in ALLOWED_PHASES:
            offenders.append(f"{page.name}: bad phase {phase!r} (allowed: {sorted(ALLOWED_PHASES)})")
        if _core_usage_first_line(text) is None:
            offenders.append(f"{page.name}: missing `## Core usage` fence with a runnable first line")
    assert not offenders, "tool-page frontmatter offenders:\n" + "\n".join(offenders)
