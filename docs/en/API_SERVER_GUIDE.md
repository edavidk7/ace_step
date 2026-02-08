# ACE-Step API Server Deployment Guide

**Language / 语言 / 言語:** [English](API_SERVER_GUIDE.md)

---

This guide covers how to install, configure, and run the ACE-Step REST API server on Linux. For the full API endpoint reference, see [API.md](API.md). For Windows `.bat` file configuration, see [BAT_CONFIGURATION.md](../../.claude/skills/acestep-docs/guides/BAT_CONFIGURATION.md).

---

## Table of Contents

- [Prerequisites](#1-prerequisites)
- [Installation](#2-installation)
- [FFmpeg / torchcodec Setup](#3-ffmpeg--torchcodec-setup)
- [Starting the Server](#4-starting-the-server)
- [CLI Arguments Reference](#5-cli-arguments-reference)
- [Environment Variables Reference](#6-environment-variables-reference)
- [LM-Only Endpoints Quick Start](#7-lm-only-endpoints-quick-start)
- [Running the Test Suite](#8-running-the-test-suite)
- [Troubleshooting](#9-troubleshooting)
- [Windows Notes](#10-windows-notes)

---

## 1. Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11+ | 3.11 |
| CUDA GPU | 6 GB VRAM (DiT only) | 24+ GB VRAM (DiT + LLM) |
| CUDA toolkit | 12.1+ | 12.4+ |
| Package manager | `uv` or `pip` | `uv` |
| OS | Linux (glibc 2.31+) | Ubuntu 22.04+ |

Models are downloaded automatically on first run from HuggingFace Hub (or ModelScope for users in China).

---

## 2. Installation

```bash
# Clone the repository
git clone https://github.com/edavidk7/ace_step.git
cd ace_step

# Create a virtual environment and install dependencies
uv venv --python 3.11
uv sync

# Or with pip:
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 3. FFmpeg / torchcodec Setup

**Why this is needed:** `torchaudio >= 2.10` defaults to the `torchcodec` backend, which requires FFmpeg shared libraries at runtime. Without them, any endpoint that loads audio files (`/lm/understand` file upload, cover, repaint, etc.) will fail with errors like:

```
RuntimeError: Failed to open the file ...
Failed to create a decoder for ... No such file or directory
```

Or `torchcodec` errors referencing missing `libavutil.so`, `libavcodec.so`, etc.

### 3.1 Install PyAV (bundles FFmpeg)

The easiest solution is to install [PyAV](https://pyav.org/), which bundles FFmpeg 8 shared libraries inside its wheel:

```bash
# With uv:
uv pip install av

# Or with pip:
pip install av
```

### 3.2 Create soname symlinks

PyAV's bundled libraries use auditwheel-mangled filenames (e.g., `libavutil-abc123.so.60.33.100`), but `torchcodec` looks for standard sonames (`libavutil.so.60`). Create symlinks to bridge the gap:

```bash
AV_LIBS=".venv/lib/python3.11/site-packages/av.libs"

ln -sf "$AV_LIBS"/libavutil-*.so.60.*    "$AV_LIBS/libavutil.so.60"
ln -sf "$AV_LIBS"/libavcodec-*.so.62.*   "$AV_LIBS/libavcodec.so.62"
ln -sf "$AV_LIBS"/libavformat-*.so.62.*  "$AV_LIBS/libavformat.so.62"
ln -sf "$AV_LIBS"/libavdevice-*.so.62.*  "$AV_LIBS/libavdevice.so.62"
ln -sf "$AV_LIBS"/libavfilter-*.so.11.*  "$AV_LIBS/libavfilter.so.11"
ln -sf "$AV_LIBS"/libswresample-*.so.6.* "$AV_LIBS/libswresample.so.6"
ln -sf "$AV_LIBS"/libswscale-*.so.9.*    "$AV_LIBS/libswscale.so.9"
```

> **Note:** Adjust the Python version in the path if you are not using Python 3.11 (e.g., `python3.12`).

### 3.3 Set LD_LIBRARY_PATH

The server process must be able to find these libraries. Set `LD_LIBRARY_PATH` before starting:

```bash
export LD_LIBRARY_PATH="$(pwd)/.venv/lib/python3.11/site-packages/av.libs:$LD_LIBRARY_PATH"
```

Or prepend it inline when launching the server (shown in [Section 4](#4-starting-the-server)).

### 3.4 Alternative: System FFmpeg

If you prefer to use a system-wide FFmpeg installation instead of PyAV:

```bash
# Ubuntu / Debian
sudo apt-get install ffmpeg libavutil-dev libavcodec-dev libavformat-dev

# The system libraries are already on the default library path,
# so no LD_LIBRARY_PATH change is needed.
```

System FFmpeg 7+ provides the required sonames. If your distro ships an older version, use the PyAV approach above.

### 3.5 Verify

```bash
# Quick check: this should print the torchaudio version without errors
LD_LIBRARY_PATH=".venv/lib/python3.11/site-packages/av.libs:$LD_LIBRARY_PATH" \
  .venv/bin/python3 -c "import torchaudio; print(torchaudio.__version__)"
```

---

## 4. Starting the Server

### 4.1 Minimal start

```bash
.venv/bin/python3 -m acestep.api_server
```

This starts on `127.0.0.1:8001` with auto GPU detection, DiT model only (LLM loaded if VRAM > 6 GB).

### 4.2 With LLM enabled

The LLM is required for the `/lm/*` endpoints, thinking mode, CoT caption/language, sample mode, and format mode.

```bash
ACESTEP_INIT_LLM=true .venv/bin/python3 -m acestep.api_server
```

Or via CLI flag:

```bash
.venv/bin/python3 -m acestep.api_server --init-llm
```

### 4.3 Selecting a specific GPU

```bash
CUDA_VISIBLE_DEVICES=1 .venv/bin/python3 -m acestep.api_server
```

### 4.4 Full production example

Combines FFmpeg library path, GPU selection, LLM initialization, API key authentication, and custom host/port:

```bash
LD_LIBRARY_PATH="$(pwd)/.venv/lib/python3.11/site-packages/av.libs:$LD_LIBRARY_PATH" \
CUDA_VISIBLE_DEVICES=1 \
ACESTEP_INIT_LLM=true \
.venv/bin/python3 -m acestep.api_server \
  --host 0.0.0.0 \
  --port 8001 \
  --api-key "your-secret-key" \
  --lm-model-path acestep-5Hz-lm-0.6B
```

### 4.5 Using a .env file

For convenience, you can put environment variables in a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
ACESTEP_INIT_LLM=true
ACESTEP_API_KEY=your-secret-key
ACESTEP_API_HOST=0.0.0.0
ACESTEP_API_PORT=8001
ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-0.6B
```

Then start normally — the server reads `.env` automatically.

---

## 5. CLI Arguments Reference

| Argument | Default | Env Var Override | Description |
|----------|---------|------------------|-------------|
| `--host` | `127.0.0.1` | `ACESTEP_API_HOST` | Server bind address |
| `--port` | `8001` | `ACESTEP_API_PORT` | Server bind port |
| `--api-key` | (none) | `ACESTEP_API_KEY` | API authentication key (empty = no auth) |
| `--download-source` | `auto` | `ACESTEP_DOWNLOAD_SOURCE` | Model download source: `auto`, `huggingface`, or `modelscope` |
| `--init-llm` | `false` | `ACESTEP_INIT_LLM` | Force LLM initialization (needed for `/lm/*` endpoints) |
| `--lm-model-path` | (auto) | `ACESTEP_LM_MODEL_PATH` | LM model name (e.g., `acestep-5Hz-lm-0.6B`, `acestep-5Hz-lm-1.7B`) |

CLI arguments take precedence over environment variables.

---

## 6. Environment Variables Reference

See also [API.md Section 12](API.md#12-environment-variables) for the full list.

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_API_HOST` | `127.0.0.1` | Server bind host |
| `ACESTEP_API_PORT` | `8001` | Server bind port |
| `ACESTEP_API_KEY` | (none) | API authentication key |

### Model

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_CONFIG_PATH` | `acestep-v15-turbo` | Primary DiT model |
| `ACESTEP_LM_MODEL_PATH` | `acestep-5Hz-lm-0.6B` | 5Hz Language Model |
| `ACESTEP_LM_BACKEND` | `vllm` | LM backend: `vllm` or `pt` |
| `ACESTEP_INIT_LLM` | `auto` | LLM initialization: `auto`, `true`, or `false` |
| `ACESTEP_DEVICE` | `auto` | Device: `auto`, `cuda`, `cpu`, `xpu` |
| `ACESTEP_DOWNLOAD_SOURCE` | `auto` | Download source: `auto`, `huggingface`, `modelscope` |

### GPU / Offload

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_USE_FLASH_ATTENTION` | `true` | Enable flash attention |
| `ACESTEP_OFFLOAD_TO_CPU` | `false` | Offload all models to CPU when idle |
| `ACESTEP_OFFLOAD_DIT_TO_CPU` | `false` | Offload DiT specifically to CPU |
| `ACESTEP_LM_OFFLOAD_TO_CPU` | `false` | Offload LM to CPU when idle |

### Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_QUEUE_MAXSIZE` | `200` | Maximum generation queue size |
| `ACESTEP_QUEUE_WORKERS` | `1` | Number of queue workers |

### Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `ACESTEP_TMPDIR` | `.cache/acestep/tmp` | Temp file directory |
| `TRITON_CACHE_DIR` | `.cache/acestep/triton` | Triton cache directory |

---

## 7. LM-Only Endpoints Quick Start

These three endpoints expose the 5Hz Language Model directly, without generating audio. They require `ACESTEP_INIT_LLM=true`.

### 7.1 Inspire — generate ideas from a description

```bash
curl -X POST http://localhost:8001/lm/inspire \
  -H 'Content-Type: application/json' \
  -d '{"query": "a melancholic jazz ballad with piano and saxophone"}'
```

Returns: `caption`, `lyrics`, `bpm`, `duration`, `key_scale`, `language`, `time_signature`.

### 7.2 Format — enhance/structure existing input

```bash
curl -X POST http://localhost:8001/lm/format \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "pop rock summer song",
    "lyrics": "Walking down the open road\nSun is shining feel the glow",
    "bpm": 128,
    "language": "en"
  }'
```

Returns the same fields as Inspire, with enhanced caption and structured lyrics.

### 7.3 Understand — analyze audio

```bash
# Upload an audio file
curl -X POST http://localhost:8001/lm/understand \
  -F "audio=@/path/to/song.mp3" \
  -F "temperature=0.3"

# Or point to a file already on the server
curl -X POST http://localhost:8001/lm/understand \
  -H 'Content-Type: application/json' \
  -d '{"audio_path": "/data/songs/example.wav"}'
```

Returns: `caption`, `lyrics`, `bpm`, `duration`, `key_scale`, `language`, `time_signature`.

For full parameter tables and response schemas, see [API.md Sections 13-15](API.md#13-lm-understand-audio).

---

## 8. Running the Test Suite

A comprehensive test script covers all three LM endpoints (13 tests):

```bash
# Basic usage (server running on localhost:8001)
.venv/bin/python3 scripts/test_lm_endpoints.py

# Custom base URL
.venv/bin/python3 scripts/test_lm_endpoints.py --base-url http://192.168.1.10:8001

# With API key authentication
.venv/bin/python3 scripts/test_lm_endpoints.py --api-key "your-secret-key"

# With an audio file for /lm/understand upload test
.venv/bin/python3 scripts/test_lm_endpoints.py --audio-file /path/to/song.mp3
```

### Test coverage

| Endpoint | Tests | What is tested |
|----------|-------|----------------|
| `/lm/inspire` | 5 | Basic, instrumental, language constraint, missing query (400), seed reproducibility |
| `/lm/format` | 4 | Basic, with constraints, caption-only, missing both fields (400) |
| `/lm/understand` | 4 | No input (400), file upload (multipart), audio_path (JSON), audio_codes if available |

All 13 tests pass on an A100-SXM4-40GB in ~40 seconds.

---

## 9. Troubleshooting

### 9.1 torchcodec / FFmpeg errors

**Symptom:**
```
RuntimeError: Failed to open the file ...
ImportError: libavutil.so.60: cannot open shared object file
```

**Fix:** Follow [Section 3](#3-ffmpeg--torchcodec-setup) — install PyAV, create symlinks, and set `LD_LIBRARY_PATH`.

### 9.2 GPU out of memory (OOM)

**Symptom:**
```
torch.cuda.OutOfMemoryError: CUDA out of memory
```

**Possible fixes:**
1. Use a smaller LM model: `--lm-model-path acestep-5Hz-lm-0.6B`
2. Enable CPU offloading: `ACESTEP_OFFLOAD_TO_CPU=true`
3. Disable the LLM if you don't need `/lm/*` endpoints: `ACESTEP_INIT_LLM=false`
4. Use the turbo DiT model (lower VRAM): `ACESTEP_CONFIG_PATH=acestep-v15-turbo`

**VRAM budget (approximate):**

| Component | VRAM |
|-----------|------|
| DiT (turbo) | ~4 GB |
| DiT (quality) | ~8 GB |
| LM 0.6B | ~4 GB |
| LM 1.7B | ~8 GB |
| Runtime overhead | ~2-4 GB |

### 9.3 Port already in use

**Symptom:**
```
OSError: [Errno 98] Address already in use
```

**Fix:** Use a different port or kill the existing process:

```bash
# Find what's using the port
lsof -i :8001

# Use a different port
.venv/bin/python3 -m acestep.api_server --port 8002
```

### 9.4 LLM not initialized

**Symptom:** `/lm/*` endpoints return `503 Service Unavailable` with message "LLM not initialized".

**Fix:** Start the server with `ACESTEP_INIT_LLM=true` or `--init-llm`. The LLM is disabled by default on GPUs with <= 6 GB VRAM.

### 9.5 Model download failures

**Symptom:** Timeouts or connection errors during first startup.

**Fix:**
```bash
# For users in China, use ModelScope:
.venv/bin/python3 -m acestep.api_server --download-source modelscope

# For users outside China:
.venv/bin/python3 -m acestep.api_server --download-source huggingface
```

### 9.6 CUDA not detected

See [GPU_TROUBLESHOOTING.md](GPU_TROUBLESHOOTING.md) for detailed GPU detection troubleshooting.

---

## 10. Windows Notes

On Windows, use the provided `.bat` scripts instead of running Python directly:

- `start_api_server.bat` — starts the API server
- `start_gradio_ui.bat` — starts the Gradio web UI

Configuration is done by editing variables at the top of each `.bat` file. See [BAT_CONFIGURATION.md](../../.claude/skills/acestep-docs/guides/BAT_CONFIGURATION.md) for details.

The FFmpeg/torchcodec issue (Section 3) does not typically occur on Windows when using the portable package, as it bundles its own Python environment with compatible dependencies.
