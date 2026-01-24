#!/usr/bin/env python3
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Audit dependency versions across all LISA components.

This script finds version inconsistencies across:
- requirements.txt files
- pyproject.toml files (both Poetry and PEP 621)
- poetry.lock files

It reports any packages that have different versions in different locations.
"""

import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path


class DependencyAuditor:
    def __init__(self, root_path: Path):
        self.root = root_path
        self.package_versions: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    def find_files(self, pattern: str, exclude_dirs: list[str] | None = None) -> list[Path]:
        """Find files matching pattern, excluding specified directories."""
        exclude_dirs = exclude_dirs or ["node_modules", ".venv", "dist", "build", ".pytest_cache"]
        files = []

        for file in self.root.rglob(pattern):
            if not any(excluded in file.parts for excluded in exclude_dirs):
                files.append(file)

        return sorted(files)

    def parse_requirement_line(self, line: str) -> tuple[str, str] | None:
        """
        Parse a requirement line into (package, version_spec).

        Returns None if line is a comment, empty, or not a simple requirement.
        """
        line = line.strip()

        # Skip comments, empty lines, and special directives
        if not line or line.startswith("#") or line.startswith("-"):
            return None

        # Handle extras like package[extra]==version
        # Match: package==version, package>=version, package[extra]==version, etc.
        match = re.match(r"^([a-zA-Z0-9_-]+)(?:\[[\w,]+\])?((?:==|>=|<=|>|<|~=|!=).+?)(?:\s|;|$)", line)
        if match:
            package, version_spec = match.groups()
            return (package.lower(), version_spec.strip())

        # Handle version-less requirements (e.g., "toml" or "langchain")
        match = re.match(r"^([a-zA-Z0-9_-]+)(?:\[[\w,]+\])?$", line)
        if match:
            package = match.group(1)
            return (package.lower(), "*")

        return None

    def audit_requirements_files(self) -> None:
        """Audit all requirements.txt files."""
        for file_path in self.find_files("requirements*.txt"):
            rel_path = str(file_path.relative_to(self.root))

            try:
                content = file_path.read_text()
                for _line_num, line in enumerate(content.split("\n"), 1):
                    parsed = self.parse_requirement_line(line)
                    if parsed:
                        package, version_spec = parsed
                        self.package_versions[package][rel_path].add(version_spec)
            except Exception as e:
                print(f"Warning: Could not parse {rel_path}: {e}", file=sys.stderr)

    def audit_pyproject_files(self) -> None:
        """Audit all pyproject.toml files."""
        for file_path in self.find_files("pyproject.toml"):
            rel_path = str(file_path.relative_to(self.root))

            try:
                with open(file_path, "rb") as f:
                    data = tomllib.load(f)

                # Check PEP 621 [project] dependencies
                if "project" in data and "dependencies" in data["project"]:
                    for dep in data["project"]["dependencies"]:
                        parsed = self.parse_requirement_line(dep)
                        if parsed:
                            package, version_spec = parsed
                            self.package_versions[package][f"{rel_path} [project]"].add(version_spec)

                # Check Poetry [tool.poetry.dependencies]
                if "tool" in data and "poetry" in data["tool"]:
                    poetry_deps = data["tool"]["poetry"].get("dependencies", {})
                    for package, spec in poetry_deps.items():
                        if package == "python":
                            continue

                        package = package.lower()

                        # Handle different Poetry version specifications
                        if isinstance(spec, str):
                            # Simple version string like "^3.13" or "*"
                            version_spec = spec
                        elif isinstance(spec, dict):
                            # Complex spec like {version = "^1.0", extras = ["proxy"]}
                            version_spec = spec.get("version", "*")
                        else:
                            version_spec = str(spec)

                        self.package_versions[package][f"{rel_path} [tool.poetry]"].add(version_spec)

                    # Check dev dependencies
                    for group_name, group_data in data["tool"]["poetry"].get("group", {}).items():
                        if "dependencies" in group_data:
                            for package, spec in group_data["dependencies"].items():
                                package = package.lower()

                                if isinstance(spec, str):
                                    version_spec = spec
                                elif isinstance(spec, dict):
                                    version_spec = spec.get("version", "*")
                                else:
                                    version_spec = str(spec)

                                self.package_versions[package][f"{rel_path} [tool.poetry.group.{group_name}]"].add(
                                    version_spec
                                )

                # Check optional dependencies
                if "project" in data and "optional-dependencies" in data["project"]:
                    for group_name, deps in data["project"]["optional-dependencies"].items():
                        for dep in deps:
                            parsed = self.parse_requirement_line(dep)
                            if parsed:
                                package, version_spec = parsed
                                self.package_versions[package][
                                    f"{rel_path} [project.optional-dependencies.{group_name}]"
                                ].add(version_spec)

            except Exception as e:
                print(f"Warning: Could not parse {rel_path}: {e}", file=sys.stderr)

    def audit_poetry_lock_files(self) -> None:
        """Audit all poetry.lock files."""
        for file_path in self.find_files("poetry.lock"):
            rel_path = str(file_path.relative_to(self.root))

            try:
                with open(file_path, "rb") as f:
                    data = tomllib.load(f)

                # Poetry lock files have a [[package]] array
                for package_data in data.get("package", []):
                    package = package_data.get("name", "").lower()
                    version = package_data.get("version", "")

                    if package and version:
                        self.package_versions[package][f"{rel_path} (locked)"].add(f"=={version}")

            except Exception as e:
                print(f"Warning: Could not parse {rel_path}: {e}", file=sys.stderr)

    def normalize_version_spec(self, spec: str) -> str:
        """Normalize version specs for comparison."""
        # Remove whitespace
        spec = spec.strip()

        # Normalize Poetry caret (^) to >= for comparison purposes
        # ^1.2.3 means >=1.2.3,<2.0.0
        if spec.startswith("^"):
            return f">={spec[1:]}"

        # Normalize Poetry tilde (~) to >= for comparison purposes
        # ~1.2.3 means >=1.2.3,<1.3.0
        if spec.startswith("~"):
            return f">={spec[1:]}"

        return spec

    def are_versions_compatible(self, specs: set[str]) -> bool:
        """
        Check if version specs are compatible.

        This is a simplified check - it considers specs compatible if:
        - They're identical
        - One is a wildcard (*)
        - They're all locked versions (==) with the same value
        """
        if len(specs) == 1:
            return True

        # Remove wildcards for comparison
        non_wildcard = {s for s in specs if s != "*"}
        if not non_wildcard:
            return True

        # Normalize specs
        normalized = {self.normalize_version_spec(s) for s in non_wildcard}

        # If all normalized specs are the same, they're compatible
        if len(normalized) == 1:
            return True

        # Check if all are exact versions (==) with same value
        exact_versions = set()
        for spec in normalized:
            if spec.startswith("=="):
                exact_versions.add(spec[2:])
            else:
                # Has range specs, might be incompatible
                return False

        # If we have multiple different exact versions, incompatible
        return len(exact_versions) <= 1

    def generate_report(self) -> tuple[dict[str, dict[str, set[str]]], int]:
        """
        Generate inconsistency report.

        Returns (inconsistencies, total_packages_checked)
        """
        inconsistencies = {}

        for package, locations in sorted(self.package_versions.items()):
            # Get all unique version specs for this package
            all_specs = set()
            for specs in locations.values():
                all_specs.update(specs)

            # Check if versions are inconsistent
            if not self.are_versions_compatible(all_specs):
                inconsistencies[package] = locations

        return inconsistencies, len(self.package_versions)

    def run_audit(self) -> int:
        """
        Run full audit and print report.

        Returns exit code (0 if no issues, 1 if inconsistencies found).
        """
        print("🔍 Auditing LISA dependency versions...\n")

        # Collect all dependency information
        print("Scanning requirements.txt files...")
        self.audit_requirements_files()

        print("Scanning pyproject.toml files...")
        self.audit_pyproject_files()

        print("Scanning poetry.lock files...")
        self.audit_poetry_lock_files()

        # Generate report
        inconsistencies, total_packages = self.generate_report()

        print(f"\n📊 Scanned {total_packages} unique packages\n")

        if not inconsistencies:
            print("✅ No version inconsistencies found!")
            return 0

        # Print inconsistencies
        print(f"⚠️  Found {len(inconsistencies)} package(s) with version inconsistencies:\n")
        print("=" * 80)

        for package, locations in sorted(inconsistencies.items()):
            print(f"\n📦 {package}")
            print("-" * 80)

            for location, specs in sorted(locations.items()):
                for spec in sorted(specs):
                    print(f"  {spec:20} in {location}")

        print("\n" + "=" * 80)
        print(f"\n❌ Found inconsistencies in {len(inconsistencies)} package(s)")
        print("\nRecommendation: Update versions to match across all files.")

        return 1


def main() -> None:

    # Find project root
    script_path = Path(__file__).resolve()
    root_path = script_path.parent.parent

    # Run audit
    auditor = DependencyAuditor(root_path)
    exit_code = auditor.run_audit()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
