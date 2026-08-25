"""Check that backend/requirements.lock stays in sync with requirements.txt.

The lock file is the single install source for Docker and CI (#102). This
script is a deterministic, offline consistency check — it does NOT re-resolve
against PyPI, so an upstream release can never break CI on its own; refreshing
the lock remains a deliberate act (see SECURITY.md for the regeneration
command). It verifies:

1. every direct dependency in requirements.txt has an exact pin in the lock;
2. each pinned version satisfies the direct dependency's specifier;
3. the lock contains no duplicate pins for the same package.

Extras (e.g. ``uvicorn[standard]``) are intentionally matched by name only:
the universal lock expands extra dependencies into their own pinned entries,
so extras carry no install semantics at lock level.

Usage: python dev_scripts/check_requirements_lock.py [REQUIREMENTS] [LOCK]
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from packaging.version import Version
except ImportError as exc:  # pragma: no cover - environment guard
    print(f"packaging is required: {exc}", file=sys.stderr)
    print("Install backend dependencies first (pip install -r requirements.lock).", file=sys.stderr)
    return_code = 2
else:

    def parse_lines(path: Path) -> list[str]:
        lines = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-"):
                raise SystemExit(f"{path}: unsupported directive line: {line}")
            lines.append(line)
        return lines

    def load_requirements(path: Path) -> dict[str, Requirement]:
        return {canonicalize_name(Requirement(line).name): Requirement(line) for line in parse_lines(path)}

    def load_lock_pins(path: Path) -> dict[str, str]:
        pins: dict[str, str] = {}
        for line in parse_lines(path):
            # Lock entries are exact pins with optional markers/extras, e.g.
            # "uvicorn[standard]==0.52.4 ; sys_platform == 'win32'".
            requirement = Requirement(line.split(";", 1)[0])
            name = canonicalize_name(requirement.name)
            specifiers = list(requirement.specifier)
            if len(specifiers) != 1 or specifiers[0].operator != "==":
                raise SystemExit(f"{path}: expected exactly one '==' pin per entry, got: {line}")
            if name in pins:
                raise SystemExit(f"{path}: duplicate pin for {name}")
            pins[name] = specifiers[0].version
        return pins

    def main() -> int:
        backend_dir = Path(__file__).resolve().parent.parent
        requirements_path = Path(sys.argv[1]) if len(sys.argv) > 1 else backend_dir / "requirements.txt"
        lock_path = Path(sys.argv[2]) if len(sys.argv) > 2 else backend_dir / "requirements.lock"

        try:
            requirements = load_requirements(requirements_path)
            pins = load_lock_pins(lock_path)
        except (OSError, ValueError) as exc:
            print(f"FAIL: could not parse inputs: {exc}", file=sys.stderr)
            return 1

        failures = []
        for name, requirement in sorted(requirements.items()):
            if name not in pins:
                failures.append(f"{requirement}: missing from {lock_path.name}")
                continue
            pinned = Version(pins[name])
            if not requirement.specifier.contains(pinned, prereleases=True):
                failures.append(
                    f"{requirement}: locked version {pins[name]} does not satisfy specifier"
                )
        extra_names = sorted(set(pins) - set(requirements))
        # Transitive pins legitimately outnumber direct deps; report them as
        # drift evidence, never as failure.
        print(
            f"info: {len(extra_names)} transitive pins beyond requirements.txt "
            f"(expected): {', '.join(extra_names)}"
        )
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            return 1

        print(
            f"OK: {lock_path.name} covers all {len(requirements)} direct dependencies "
            f"({len(pins)} total pins); regenerate via uv pip compile --universal "
            f"--python-version 3.11 requirements.txt -o requirements.lock"
        )
        return 0

    return_code = main()

sys.exit(return_code)
