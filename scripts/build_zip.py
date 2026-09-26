"""웹 업로드용 ZIP과 GitHub Actions 경로가 포함된 Git-ready ZIP을 생성한다."""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "JY_LGE.zip"
DEFAULT_GITHUB_READY_OUTPUT = ROOT.parent / "JY_LGE_GitHub_Ready.zip"
ARCHIVE_ROOT = "JY_LGE"


def excluded(path: Path, include_github: bool) -> bool:
    parts = path.relative_to(ROOT).parts
    if any(part in {".git", ".openai", "__pycache__"} for part in parts):
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    return any(part.startswith(".") for part in parts) and not (include_github and parts[0] in {".github", ".gitignore"})


def create_zip(output: Path, include_github: bool) -> int:
    files = [p for p in ROOT.rglob("*") if p.is_file() and not excluded(p, include_github) and p.resolve() != output]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(files):
            relative = Path(ARCHIVE_ROOT) / path.relative_to(ROOT)
            info = ZipInfo(str(relative).replace("\\", "/"), date_time=(2021, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--github-ready-output", type=Path, default=DEFAULT_GITHUB_READY_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    github_ready_output = args.github_ready_output.resolve()
    count = create_zip(output, include_github=False)
    ready_count = create_zip(github_ready_output, include_github=True)
    print(f"웹 업로드용 ZIP 생성: {output} ({count} files)")
    print(f"Git-ready ZIP 생성: {github_ready_output} ({ready_count} files)")
    with ZipFile(output) as archive:
        hidden_entries = [name for name in archive.namelist() if any(part.startswith(".") for part in Path(name).parts)]
    if hidden_entries:
        raise RuntimeError(f"숨김 항목이 ZIP에 포함되었습니다: {hidden_entries}")
    with ZipFile(github_ready_output) as archive:
        required = f"{ARCHIVE_ROOT}/.github/workflows/update-and-deploy.yml"
        if required not in archive.namelist():
            raise RuntimeError(f"Git-ready ZIP에 워크플로가 없습니다: {required}")


if __name__ == "__main__":
    main()
