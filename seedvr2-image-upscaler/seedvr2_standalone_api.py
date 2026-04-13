from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette.responses import Response


@dataclass(frozen=True)
class SeedVR2WorkflowDefaults:
    """Defaults copied from seedvr2-image-upscaler-v1 workflow nodes."""

    dit_model: str = "seedvr2_ema_7b_fp16.safetensors"
    vae_model: str = "ema_vae_fp16.safetensors"
    resolution: int = 3840
    max_resolution: int = 0
    batch_size: int = 1
    uniform_batch_size: bool = False
    color_correction: str = "lab"
    temporal_overlap: int = 0
    prepend_frames: int = 0
    input_noise_scale: float = 0.0
    latent_noise_scale: float = 0.0
    blocks_to_swap: int = 0
    swap_io_components: bool = False
    dit_offload_device: str = "cpu"
    vae_offload_device: str = "cpu"
    cache_dit: bool = True
    cache_vae: bool = True
    attention_mode: str = "sdpa"


DEFAULTS = SeedVR2WorkflowDefaults()


def _seedvr2_repo_dir() -> Path:
    env = os.getenv("SEEDVR2_REPO_DIR")
    if not env:
        raise RuntimeError(
            "SEEDVR2_REPO_DIR is not set. Point it to the cloned ComfyUI-SeedVR2_VideoUpscaler directory."
        )
    path = Path(env).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"SEEDVR2_REPO_DIR does not exist: {path}")
    return path


def _inference_cli_path() -> Path:
    repo = _seedvr2_repo_dir()
    cli = repo / "inference_cli.py"
    if not cli.exists():
        raise RuntimeError(f"SeedVR2 CLI script not found: {cli}")
    return cli


def _python_bin() -> str:
    return os.getenv("SEEDVR2_PYTHON_BIN", "python3")


def upscale_image(
    input_image_path: str | Path,
    output_image_path: str | Path,
    *,
    seed: int | None = None,
    model_dir: str | Path | None = None,
    defaults: SeedVR2WorkflowDefaults = DEFAULTS,
) -> Path:
    """Run standalone SeedVR2 on one image and write a PNG output."""
    input_image_path = Path(input_image_path).resolve()
    output_image_path = Path(output_image_path).resolve()

    if not input_image_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_image_path}")

    seed_value = random.randint(0, 2_147_483_647) if seed is None else int(seed)
    resolved_model_dir = Path(
        os.getenv("MODEL_DIR", "models/SEEDVR2") if model_dir is None else model_dir
    ).resolve()

    cmd = [
        _python_bin(),
        str(_inference_cli_path()),
        str(input_image_path),
        "--output",
        str(output_image_path),
        "--output_format",
        "png",
        "--model_dir",
        str(resolved_model_dir),
        "--dit_model",
        defaults.dit_model,
        "--resolution",
        str(defaults.resolution),
        "--max_resolution",
        str(defaults.max_resolution),
        "--batch_size",
        str(defaults.batch_size),
        "--seed",
        str(seed_value),
        "--color_correction",
        defaults.color_correction,
        "--temporal_overlap",
        str(defaults.temporal_overlap),
        "--prepend_frames",
        str(defaults.prepend_frames),
        "--input_noise_scale",
        str(defaults.input_noise_scale),
        "--latent_noise_scale",
        str(defaults.latent_noise_scale),
        "--blocks_to_swap",
        str(defaults.blocks_to_swap),
        "--dit_offload_device",
        defaults.dit_offload_device,
        "--vae_offload_device",
        defaults.vae_offload_device,
        "--attention_mode",
        defaults.attention_mode,
    ]

    if defaults.uniform_batch_size:
        cmd.append("--uniform_batch_size")
    if defaults.swap_io_components:
        cmd.append("--swap_io_components")
    if defaults.cache_dit:
        cmd.append("--cache_dit")
    if defaults.cache_vae:
        cmd.append("--cache_vae")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "SeedVR2 upscaling failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stdout:\n{result.stdout}\n"
            f"Stderr:\n{result.stderr}"
        )

    if not output_image_path.exists():
        raise RuntimeError(
            "SeedVR2 command completed but output file was not created.\n"
            f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
        )

    return output_image_path


app = FastAPI(title="SeedVR2 Standalone API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upscale")
def upscale(
    image: UploadFile = File(...),
    seed: int | None = Form(default=None),
) -> Response:
    content_type = (image.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    suffix = Path(image.filename or "input.png").suffix or ".png"
    if suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        suffix = ".png"

    with tempfile.TemporaryDirectory(prefix="seedvr2-api-") as td:
        in_path = Path(td) / f"input{suffix}"
        out_path = Path(td) / "output.png"

        with in_path.open("wb") as f:
            shutil.copyfileobj(image.file, f)

        try:
            upscale_image(in_path, out_path, seed=seed)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        output_bytes = out_path.read_bytes()
        return Response(
            content=output_bytes,
            media_type="image/png",
            headers={"Content-Disposition": 'inline; filename="upscaled.png"'},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("seedvr2_standalone_api:app", host="0.0.0.0", port=8000, reload=False)
