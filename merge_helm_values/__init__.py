#!/usr/bin/env python3

import argparse
import glob
import os
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any

import ruamel.yaml
import yaml
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString


def _commented_map(data: Any, file_name: str) -> Any:
    if isinstance(data, dict):
        new_data = {
            key: LiteralScalarString(value) if isinstance(value, str) and "\n" in value else value
            for key, value in data.items()
        }
        cm = CommentedMap({key: _commented_map(value, file_name) for key, value in new_data.items()})
        for key, value in data.items():
            if not isinstance(value, dict):
                cm.yaml_add_eol_comment(key=key, comment=f"from {file_name}")
        return cm
    return data


def _deep_merge(base: dict[str, Any], other: dict[str, Any], other_file_name: str) -> None:
    for key, value in other.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value, other_file_name)
        else:
            if isinstance(value, dict):
                base[key] = _commented_map(value, other_file_name)
            else:
                if isinstance(value, str) and "\n" in value:
                    base[key] = LiteralScalarString(value)
                else:
                    base[key] = value
                base.yaml_add_eol_comment(key=key, comment=f"from {other_file_name}")  # type: ignore[attr-defined]


def main() -> None:
    """Merge the HELM values files into a single file."""
    parser = argparse.ArgumentParser(description="Merge the HELM values files into a single file")
    default_helmfile = "**/helmfile-base.yaml"
    parser.add_argument(
        "--helmfile",
        help=f"Unix style pathname pattern expansion used to find the Helmfile files, default is {default_helmfile}",
        default=default_helmfile,
    )
    parser.add_argument(
        "--pre-commit",
        help="Run pre-commit hooks to call on the modified files (comma separated)",
    )
    default_pre_commit_skip = "merge-helm-values"
    parser.add_argument(
        "--pre-commit-skip",
        help=f"Skip the pre-commit hooks, default is {default_pre_commit_skip}",
        default=default_pre_commit_skip,
    )
    parser.add_argument(
        "--no-pre-commit",
        action="store_true",
        help="Do not run pre-commit hooks",
    )
    parser.add_argument(
        "--ignore-folder",
        help="Ignore the folder when looking for the Helmfile files",
        action="append",
        default=[],
    )
    parser.add_argument("input", nargs="*", help="The yaml modified files")

    args = parser.parse_args()

    ignore_folders = [Path(folder) for folder in args.ignore_folder]
    ruamel_yaml = ruamel.yaml.YAML()

    helmfile_filenames: set[Path] = set()
    if args.input:
        refs: dict[Path, list[Path]] = {}
        for helmfiles_filename in glob.glob(args.helmfile, recursive=True):
            helmfiles_filename_path = Path(helmfiles_filename)
            ignore = False
            for ignore_folder in ignore_folders:
                if ignore_folder in helmfiles_filename_path.parents:
                    ignore = True
                    break
            if ignore:
                continue

            if helmfiles_filename in args.input:
                helmfile_filenames.add(Path(helmfiles_filename))
                continue

            with open(helmfiles_filename, encoding="utf-8") as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
                for release in data["releases"]:
                    for value_filename in release.get("values", []):
                        real_value_filename = (
                            Path(helmfiles_filename).parent.joinpath(value_filename).resolve()
                        )
                        refs.setdefault(real_value_filename, []).append(Path(helmfiles_filename))
        for filename in args.input:
            pathname = Path(filename).resolve()
            if pathname in refs:
                for helmfile_filename in refs[pathname]:
                    helmfile_filenames.add(helmfile_filename)
    else:
        helmfile_filenames = {Path(filename) for filename in glob.glob(args.helmfile, recursive=True)}
        for ignore_folder in ignore_folders:
            helmfile_filenames = {
                helmfile_filename
                for helmfile_filename in helmfile_filenames
                if ignore_folder not in helmfile_filename.parents
            }

    print("Found helmfiles:")
    for helmfile_filename in helmfile_filenames:
        print(f"  {helmfile_filename}")
    print()

    values_filenames = []
    for helmfile_filename in helmfile_filenames:
        with helmfile_filename.open() as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
        assert len(data["releases"]) == 1, f"Expected only one release in {helmfile_filename}"
        for release in data["releases"]:
            values = CommentedMap()
            for value_filename in release.get("values", []):
                real_value_filename = helmfile_filename.parent.joinpath(value_filename)
                if not real_value_filename.exists():
                    print(f"File {real_value_filename} does not exist")
                    continue
                with open(real_value_filename, encoding="utf-8") as f:
                    _deep_merge(
                        values,
                        yaml.load(f, Loader=yaml.SafeLoader),
                        str(real_value_filename.resolve().relative_to(os.getcwd())),
                    )
            values_filename = helmfile_filename.parent.joinpath("values.yaml")
            if args.no_pre_commit:
                print(f"Updating {values_filename}")
                with values_filename.open("w") as f:
                    ruamel_yaml.dump(values, f)
            else:
                original = ""
                if values_filename.exists():
                    with values_filename.open() as f:
                        original = yaml.dump(yaml.load(f, Loader=yaml.SafeLoader), default_flow_style=False)

                # Update the file if there is a change
                values_str = StringIO()
                ruamel_yaml.dump(values, values_str)
                if original != yaml.dump(
                    yaml.load(values_str.getvalue(), Loader=yaml.SafeLoader), default_flow_style=False
                ):
                    values_filenames.append(values_filename)
                    print(f"Updating {values_filename}")
                    with values_filename.open("w") as f:
                        ruamel_yaml.dump(values, f)

    if not values_filenames:
        return

    if not args.no_pre_commit and args.pre_commit is not None:
        subprocess.run(  # noqa: S603  # pylint: disable=subprocess-run-check
            [  # noqa: S607
                "pre-commit",
                "run",
                "--color=never",
                *(args.pre_commit.split(",") if args.pre_commit else []),
                *[f"--files={filename}" for filename in values_filenames],
            ],
            env=(
                {**os.environ, "SKIP": args.pre_commit_skip}
                if args.pre_commit_skip is not None
                else os.environ
            ),
        )


if __name__ == "__main__":
    main()
