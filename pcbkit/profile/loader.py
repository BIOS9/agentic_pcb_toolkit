"""Find and load fabricator profiles."""

from __future__ import annotations

from pathlib import Path

import yaml

from pcbkit.profile.models import Profile

# Profiles shipped with pcbkit. A project gets its own copy at `pcbkit new`
# (see M3 spec): a board revised in two years must regenerate the same rules,
# so the profile travels with it rather than being referenced by name.
BUILTIN_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"

DEFAULT_PROFILE = "jlcpcb"


class ProfileError(RuntimeError):
    """A profile could not be found, parsed, or validated."""


def search_paths(project: Path | None = None) -> list[Path]:
    """Where a profile name is looked up, nearest first."""
    paths = []
    if project is not None:
        paths.append(Path(project) / "profiles")
    paths.append(BUILTIN_DIR)
    return paths


def available(project: Path | None = None) -> list[str]:
    names: list[str] = []
    for directory in search_paths(project):
        if directory.is_dir():
            names.extend(sorted(p.stem for p in directory.glob("*.yaml")))
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def load(name_or_path: str | Path = DEFAULT_PROFILE, *, project: Path | None = None) -> Profile:
    """Load a profile by name or by explicit path.

    Validation failures name the file, because a profile is data a human edits
    and a pydantic traceback with no filename is unhelpful.
    """
    candidate = Path(name_or_path)
    if candidate.suffix in {".yaml", ".yml"}:
        path = candidate
        if not path.is_file():
            raise ProfileError(f"no such profile file: {path}")
    else:
        for directory in search_paths(project):
            trial = directory / f"{name_or_path}.yaml"
            if trial.is_file():
                path = trial
                break
        else:
            known = ", ".join(available(project)) or "none found"
            raise ProfileError(
                f"unknown profile {str(name_or_path)!r}; available: {known}"
            )

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError(f"{path}: expected a mapping at the top level")

    try:
        return Profile.model_validate(raw)
    except Exception as exc:
        raise ProfileError(f"{path}: {exc}") from exc
