#!/usr/bin/env python3
"""Download and convert PyTorch model files from a project manifest.

This rewrites old-style torch serialization files into the newer zipfile
serialization format required by ComfyUI's --mmap-torch-files mode.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


TORCH_EXTENSIONS = {".ckpt", ".pt", ".pth"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download torch model files listed in a project JSON manifest and "
            "re-save them with zipfile serialization for mmap compatibility."
        )
    )
    parser.add_argument("manifest", type=Path, help="Project JSON manifest")
    parser.add_argument(
        "--comfy-dir",
        type=Path,
        default=Path.cwd(),
        help="ComfyUI root directory used for manifest target paths (default: cwd)",
    )
    parser.add_argument(
        "--flat-output-dir",
        type=Path,
        help=(
            "Save converted files directly in this directory using their basename "
            "instead of the manifest target path."
        ),
    )
    parser.add_argument(
        "--target",
        action="append",
        help=(
            "Only convert this manifest target. Can be passed multiple times. "
            "Defaults to all .pt/.pth/.ckpt entries."
        ),
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional filename extension to include, e.g. .bin",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Download from the manifest URL even when the target file already exists.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Keep a .bak copy before replacing the converted file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matching manifest entries without downloading or converting.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable HTTPS certificate verification for downloads.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def iter_file_entries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    entries = manifest.get("files", [])
    if not isinstance(entries, list):
        raise ValueError("manifest 'files' must be an array")

    result: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"files[{index}] must be an object")
        url = entry.get("url")
        target = entry.get("target")
        if not isinstance(url, str) or not isinstance(target, str):
            raise ValueError(f"files[{index}] must have string 'url' and 'target'")
        result.append({"url": url, "target": target})
    return result


def auth_headers() -> dict[str, str]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def download(url: str, path: Path, insecure: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=auth_headers())
    context = ssl._create_unverified_context() if insecure else None

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".download", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        with urllib.request.urlopen(request, context=context) as response, tmp_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def convert(path: Path, keep_backup: bool) -> None:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch is required; run this inside the ComfyUI Python environment") from exc

    obj = torch.load(path, map_location="cpu", weights_only=False)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".converted", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        torch.save(obj, tmp_path, _use_new_zipfile_serialization=True)
        if keep_backup:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    comfy_dir = args.comfy_dir.resolve()
    flat_output_dir = args.flat_output_dir.resolve() if args.flat_output_dir else None
    selected_targets = set(args.target or [])
    extensions = TORCH_EXTENSIONS | {ext if ext.startswith(".") else f".{ext}" for ext in args.include}

    entries = []
    for entry in iter_file_entries(manifest):
        target = entry["target"]
        if selected_targets and target not in selected_targets:
            continue
        if Path(target).suffix not in extensions:
            continue
        if entry["url"].startswith("TODO_URL_FOR_"):
            print(f"SKIP {target}: placeholder URL")
            continue
        entries.append(entry)

    if not entries:
        print("No matching torch model entries found.")
        return 0

    for entry in entries:
        target = entry["target"]
        path = flat_output_dir / Path(target).name if flat_output_dir else comfy_dir / target

        if args.dry_run:
            action = "download+convert" if args.force_download or not path.exists() else "convert"
            print(f"DRY-RUN {action} {path} <- {entry['url']}")
            continue

        if args.force_download or not path.exists():
            print(f"DOWNLOAD {path}")
            download(entry["url"], path, args.insecure)
        else:
            print(f"EXISTS {path}")

        print(f"CONVERT {path}")
        convert(path, args.backup)
        print(f"DONE {path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
