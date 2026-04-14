# SeedVR2 Standalone API (No ComfyUI Runtime)

This wrapper exposes SeedVR2 as a simple HTTP API:

- Input: image upload
- Output: upscaled image (`image/png`)

It reuses the standalone `inference_cli.py` from `ComfyUI-SeedVR2_VideoUpscaler` and applies defaults from your workflow (`seedvr2-image-upscaler-v1`):

- `dit_model=seedvr2_ema_7b_fp16.safetensors`
- `resolution=3840`
- `max_resolution=0`
- `batch_size=1`
- `color_correction=lab`
- `temporal_overlap=0`
- `prepend_frames=0`
- `input_noise_scale=0`
- `latent_noise_scale=0`
- `blocks_to_swap=0`
- `dit_offload_device=cpu`
- `vae_offload_device=cpu`
- `cache_dit=true`
- `cache_vae=true`
- `attention_mode=sdpa`

## 1. Clone SeedVR2 standalone repo

```bash
git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git external/ComfyUI-SeedVR2_VideoUpscaler
```

## 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r external/ComfyUI-SeedVR2_VideoUpscaler/requirements.txt
pip install -r requirements.seedvr2-standalone-api.txt
```

## 3. Download models (from your manifest)

```bash
mkdir -p models/SEEDVR2
curl -L "https://huggingface.co/avatary-ai/files/resolve/main/seedvr2_ema_7b_fp16.safetensors" -o models/SEEDVR2/seedvr2_ema_7b_fp16.safetensors
curl -L "https://huggingface.co/avatary-ai/files/resolve/main/ema_vae_fp16.safetensors" -o models/SEEDVR2/ema_vae_fp16.safetensors
```

## 4. Run API

```bash
export SEEDVR2_REPO_DIR="$(pwd)/external/ComfyUI-SeedVR2_VideoUpscaler"
# optional: export SEEDVR2_PYTHON_BIN="$(pwd)/.venv/bin/python"

uvicorn seedvr2_standalone_api:app --host 0.0.0.0 --port 8000
```

## 5. Call API

```bash
curl -X POST "http://localhost:8000/upscale" \
  -F "image=@/absolute/path/to/input.png" \
  -o upscaled.png
```

Optional seed:

```bash
curl -X POST "http://localhost:8000/upscale" \
  -F "image=@/absolute/path/to/input.png" \
  -F "seed=12345" \
  -o upscaled.png
```

## Docker (GPU)

Build:

```bash
docker build -f Dockerfile.seedvr2-standalone-api -t seedvr2-standalone-api:latest .
```

Run (mount your model folder):

```bash
docker run --rm -it \
  --gpus all \
  -p 8000:8000 \
  -v "$(pwd)/models/SEEDVR2:/app/models/SEEDVR2" \
  seedvr2-standalone-api:latest
```

Test:

```bash
curl -X POST "http://localhost:8000/upscale" \
  -F "image=@/absolute/path/to/input.png" \
  -o upscaled.png
```
