# StreamDL

[![Maintainability](https://api.codeclimate.com/v1/badges/5145a4b986526fa4573b/maintainability)](https://codeclimate.com/github/dangeroustech/StreamDL/maintainability)

![Master](https://github.com/dangeroustech/streamdl/actions/workflows/deploy_master.yml/badge.svg)
![Staging](https://github.com/dangeroustech/streamdl/actions/workflows/deploy_staging.yml/badge.svg)

![CodeQL Analysis](https://github.com/dangeroustech/streamdl/actions/workflows/codeql-analysis.yml/badge.svg)

Monitor and Download Streams from a Variety of Websites

## Why This Exists

Because there are certain streaming websites that don't store historic VODs.

This is sad.

As a nerd, you probably have terabytes of storage somewhere, right?

Why not get some use out of it? Archivists everywhere, rejoice!

## Usage

| Flag | Description | Default |
|------|-------------|---------|
| `-h`, `--help` | Show this help message and exit | - |
| `-config` | Location of config file (full path inc filename) | `config.yml` |
| `-out` | Location of output file (folder only) | Current directory |
| `-move` | Location to move completed downloads to | - |
| `-time` | Time interval to check for streams (in seconds) | `60` |
| `-batch` | Time betwen URL checks (seconds): increase for rate limiting | `5` |
| `-subfolder` | Add streams to a subfolder with the channel name | `false` |
| `-log-level` | Set logging level (debug, info, warn, error, etc) | `info` |

## Install

### Docker

- Built on Docker 19.03.4
- Built on Docker-Compose 1.24.1

If you'd like to tweak individual parameters, the Dockerfile provided can be used.

Edit the Environment variables in `docker-compose.yml.example` to modify script functionality.

Otherwise, just rename it to `docker-compose.yml` and run `docker compose up -d`.

Logs are piped to stdout by default so that `docker compose logs` works.
_If you know what you're doing, you can change this value in `entrypoint.sh`._
_Make sure to rebuild the container with `docker compose build` after editing this._

### Bare Metal

Requirements:

- Python 3.10 or newer
- ffmpeg
- uv (`pip install uv` or `pip3 install uv` depending on your system)

#### Example Run

```shell
# Clone the repository
git clone https://github.com/dangeroustech/streamdl && cd streamdl

# Create virtual environment
uv venv

# Install dependencies
uv pip install .

# Run StreamDL
uv run python streamdl.py -config ./config/config.yml -time 300
```

## Config File

Basic YAML format. See `config/config.yaml.example` for a couple of test sites.

```yaml
- site: twitch.tv
  channels:
    - name: kaypealol
      quality: best
    - name: day9tv
      quality: worst
- site: mixer.com
  channels:
    - name: ninja
      quality: best
```

## Env File

To use the `.env` file:

1. Locate the `.env.example` file.
2. Rename it to `.env` and confirm that the variables are to your liking.
   For instance, `STREAMDL_GRPC_PORT=50051` sets the gRPC port for the StreamDL service.
3. To modify any variable, open the `.env` file, change the value, and save the file.
   For example, to change the gRPC port, you might modify the line to `STREAMDL_GRPC_PORT=50052`.
