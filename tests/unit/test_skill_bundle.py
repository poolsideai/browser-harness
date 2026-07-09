"""Guard: the console-ingested browser-harness skill stays self-contained.

The poolside console discovers skills by scanning for `**/SKILL.md`, skips
symlinks during upload, and requires the SKILL.md's parent directory name to
equal its frontmatter `name` -- so `skills/browser-harness/SKILL.md` must be a
real file. On download it tars the whole `skills/browser-harness/` directory and
hands it to the agent, so every guide the skill references must be bundled inside
that directory (not fetched over the network) and must not drift from the repo's
canonical copies.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "browser-harness"
SKILL_MD = SKILL_DIR / "SKILL.md"
BUNDLED_GUIDES = SKILL_DIR / "interaction-skills"
CANONICAL_GUIDES = REPO_ROOT / "interaction-skills"


def _listed_guides() -> list[str]:
    text = SKILL_MD.read_text()
    section = text[text.index("## Interaction Skills"):]
    end = section.find("\n## ", 1)
    if end != -1:
        section = section[:end]
    return re.findall(r"^- (\S+\.md)$", section, flags=re.MULTILINE)


def test_discoverable_skill_is_a_real_file_not_a_symlink():
    # Ingestion skips symlinks, so a symlinked SKILL.md would never register.
    assert SKILL_MD.is_file() and not SKILL_MD.is_symlink()


def test_skill_does_not_fetch_guides_over_the_network():
    text = SKILL_MD.read_text()
    assert "github.com/poolsideai/browser-harness/blob" not in text
    assert "github.com/poolsideai/browser-harness/tree" not in text


def test_every_listed_guide_is_bundled_and_matches_canonical():
    listed = _listed_guides()
    assert listed, "expected a bulleted interaction-skills list in SKILL.md"
    for name in listed:
        bundled = BUNDLED_GUIDES / name
        assert bundled.is_file(), (
            f"{name} is listed in SKILL.md but not bundled under "
            "skills/browser-harness/interaction-skills/"
        )
        assert not bundled.is_symlink(), f"{name} must be a real file, not a symlink"
        assert bundled.read_bytes() == (CANONICAL_GUIDES / name).read_bytes(), (
            f"bundled {name} drifted from interaction-skills/{name}"
        )


def test_install_reference_is_bundled():
    assert (SKILL_DIR / "references" / "install.md").is_file()
