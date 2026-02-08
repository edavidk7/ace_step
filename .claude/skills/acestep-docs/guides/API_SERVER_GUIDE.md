# API Server Deployment Guide

Comprehensive guide for deploying the ACE-Step REST API server on Linux.

Full version: `docs/en/API_SERVER_GUIDE.md`

## Prerequisites

- Python 3.11+, CUDA GPU (6+ GB VRAM, 24+ GB recommended for DiT + LLM), `uv` package manager

## FFmpeg / torchcodec Setup

`torchaudio >= 2.10` defaults to `torchcodec` backend, which requires FFmpeg shared libraries. Without them, audio file loading fails (affects `/lm/understand` file upload, cover, repaint).

### Fix: Install PyAV + create symlinks

```bash
# 1. Install PyAV (bundles FFmpeg 8)
uv pip install av

# 2. Create soname symlinks
AV_LIBS=".venv/lib/python3.11/site-packages/av.libs"
ln -sf "$AV_LIBS"/libavutil-*.so.60.*    "$AV_LIBS/libavutil.so.60"
ln -sf "$AV_LIBS"/libavcodec-*.so.62.*   "$AV_LIBS/libavcodec.so.62"
ln -sf "$AV_LIBS"/libavformat-*.so.62.*  "$AV_LIBS/libavformat.so.62"
ln -sf "$AV_LIBS"/libavdevice-*.so.62.*  "$AV_LIBS/libavdevice.so.62"
ln -sf "$AV_LIBS"/libavfilter-*.so.11.*  "$AV_LIBS/libavfilter.so.11"
ln -sf "$AV_LIBS"/libswresample-*.so.6.* "$AV_LIBS/libswresample.so.6"
ln -sf "$AV_LIBS"/libswscale-*.so.9.*    "$AV_LIBS/libswscale.so.9"

# 3. Set LD_LIBRARY_PATH when starting the server
export LD_LIBRARY_PATH="$(pwd)/.venv/lib/python3.11/site-packages/av.libs:$LD_LIBRARY_PATH"
```

Alternative: Install system FFmpeg 7+ (`sudo apt-get install ffmpeg libavutil-dev libavcodec-dev libavformat-dev`).

## Starting the Server

### Minimal
```bash
.venv/bin/python3 -m acestep.api_server
```

### Full production example
```bash
LD_LIBRARY_PATH="$(pwd)/.venv/lib/python3.11/site-packages/av.libs:$LD_LIBRARY_PATH" \
CUDA_VISIBLE_DEVICES=1 \
ACESTEP_INIT_LLM=true \
.venv/bin/python3 -m acestep.api_server \
  --host 0.0.0.0 --port 8001 \
  --api-key "your-secret-key" \
  --lm-model-path acestep-5Hz-lm-0.6B
```

## CLI Arguments

| Argument | Default | Env Var | Description |
|----------|---------|---------|-------------|
| `--host` | `127.0.0.1` | `ACESTEP_API_HOST` | Bind address |
| `--port` | `8001` | `ACESTEP_API_PORT` | Bind port |
| `--api-key` | (none) | `ACESTEP_API_KEY` | Auth key |
| `--download-source` | `auto` | `ACESTEP_DOWNLOAD_SOURCE` | `auto`, `huggingface`, `modelscope` |
| `--init-llm` | `false` | `ACESTEP_INIT_LLM` | Force LLM init (required for `/lm/*`) |
| `--lm-model-path` | (auto) | `ACESTEP_LM_MODEL_PATH` | LM model name |

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_INIT_LLM` | `auto` | `auto`, `true`, `false` — controls LLM loading |
| `ACESTEP_CONFIG_PATH` | `acestep-v15-turbo` | DiT model |
| `ACESTEP_LM_MODEL_PATH` | `acestep-5Hz-lm-0.6B` | LM model |
| `ACESTEP_LM_BACKEND` | `vllm` | `vllm` or `pt` |
| `ACESTEP_OFFLOAD_TO_CPU` | `false` | CPU offload for low VRAM |

## LM Endpoints Quick Reference

Require `ACESTEP_INIT_LLM=true`. All synchronous, no audio generation.

- **`POST /lm/inspire`** — Generate caption/lyrics/metadata from a text description
- **`POST /lm/format`** — Enhance/structure existing caption + lyrics
- **`POST /lm/understand`** — Analyze audio file, extract caption/lyrics/metadata

See `docs/en/API.md` sections 13-15 for full specs.

## Test Script

```bash
.venv/bin/python3 scripts/test_lm_endpoints.py [--base-url URL] [--api-key KEY] [--audio-file PATH]
```

13 tests covering all 3 endpoints (inspire, format, understand). ~40s on A100.

## Common Issues

| Problem | Fix |
|---------|-----|
| `libavutil.so.60: cannot open` | Install PyAV, create symlinks, set `LD_LIBRARY_PATH` |
| OOM errors | Use 0.6B LM, enable `ACESTEP_OFFLOAD_TO_CPU=true`, or disable LLM |
| `/lm/*` returns 503 | Start with `ACESTEP_INIT_LLM=true` |
| Port in use | `--port 8002` or `lsof -i :8001` to find conflicting process |
| Download failures | `--download-source modelscope` (China) or `huggingface` |
