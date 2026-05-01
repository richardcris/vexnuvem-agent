from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path
import os
import tomllib


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = ROOT / "pyproject.toml"
OUTPUT_FILE = ROOT / "src" / "vexnuvem_agent" / "_build_meta.py"


def load_base_version() -> str:
    payload = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))
    version = str(payload.get("project", {}).get("version", "1.0.0")).strip()
    return version or "1.0.0"


def resolve_repository(raw_value: str) -> str:
    clean = (raw_value or "").strip().strip("/")
    if not clean:
        return ""
    clean = clean.removeprefix("https://github.com/").removeprefix("http://github.com/")
    parts = [part for part in clean.split("/") if part]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def write_build_metadata(build_version: str, github_repository: str) -> None:
    content = (
        '"""Arquivo gerado automaticamente pelos scripts de build."""\n\n'
        f'BUILD_VERSION = "{build_version}"\n'
        f'GITHUB_REPOSITORY = "{github_repository}"\n'
    )
    OUTPUT_FILE.write_text(content, encoding="utf-8")


def main() -> None:
    parser = ArgumentParser(description="Gera os metadados de build do VexNuvem Agent.")
    parser.add_argument("--version", default="", help="Versao final que sera embutida no executavel.")
    parser.add_argument("--repository", default="", help="Repositorio GitHub no formato usuario/repositorio.")
    args = parser.parse_args()

    base_version = load_base_version()
    build_version = (args.version or os.getenv("VEXNUVEM_BUILD_VERSION") or base_version).strip() or base_version
    github_repository = resolve_repository(
        args.repository or os.getenv("VEXNUVEM_GITHUB_REPOSITORY") or os.getenv("GITHUB_REPOSITORY") or ""
    )

    write_build_metadata(build_version, github_repository)
    print(
        json.dumps(
            {
                "build_version": build_version,
                "github_repository": github_repository,
                "output_file": str(OUTPUT_FILE),
            }
        )
    )


if __name__ == "__main__":
    main()