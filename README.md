# StreamDL

[![Maintainability](https://api.codeclimate.com/v1/badges/5145a4b986526fa4573b/maintainability)](https://codeclimate.com/github/dangeroustech/StreamDL/maintainability)

![Master](https://github.com/dangeroustech/streamdl/actions/workflows/deploy_master.yml/badge.svg)
![Staging](https://github.com/dangeroustech/streamdl/actions/workflows/deploy_staging.yml/badge.svg)

Monitor and Download Streams from a Variety of Websites

## Why This Exists

Because there are certain streaming websites that don't store historic VODs.

This is sad.

As a nerd, you probably have terabytes of storage somewhere, right?

Why not get some use out of it? Archivists everywhere, rejoice!

## Usage

| Flag           | Description                                                  | Default           |
| -------------- | ------------------------------------------------------------ | ----------------- |
| `-h`, `--help` | Show this help message and exit                              | -                 |
| `-config`      | Location of config file (full path inc filename)             | `config.yml`      |
| `-out`         | Location of output file (folder only)                        | Current directory |
| `-move`        | Location to move completed downloads to                      | -                 |
| `-time`        | Time interval to check for streams (in seconds)              | `60`              |
| `-batch`       | Time betwen URL checks (seconds): increase for rate limiting | `5`               |
| `-subfolder`   | Add streams to a subfolder with the channel name             | `false`           |
| `-log-level`   | Set logging level (debug, info, warn, error, etc)            | `info`            |
| `-data`        | Directory for persistent data (VOD tracking database)        | `/app/data`       |
| `-vod-out`     | Output location for VOD downloads (defaults to `-out`)       | Same as `-out`    |
| `-vod-move`    | Move location for completed VOD downloads (defaults to `-move`) | Same as `-move` |

## Install

### Docker

- Built on Docker 19.03.4
- Built on Docker-Compose 1.24.1

If you'd like to tweak individual parameters, the Dockerfile provided can be used.

Edit the Environment variables in `docker-compose.yml.example` to modify script functionality.

Otherwise, just rename it to `docker-compose.yml` and run `docker compose up -d`.

#### Security Best Practices

StreamDL containers drop privileges at runtime by switching to a non-root user:

- **Default Runtime User**: Entrypoints create/use a `streamdl` user with UID 1000 and GID 1000 unless `PUID`/`PGID` override them
- **Runtime User Switching**: Supports dynamic UID/GID switching via `PUID`/`PGID` environment variables
- **User Tools**: Uses `su-exec` (client) and `gosu` (server) for secure user switching
- **Directory Permissions**: Entrypoints create the directories they manage at startup

##### Directory Permissions

When using Docker, be aware of the following:

- It's recommended to create the download directories **before** running the container
- All directories mounted in Docker will have their permissions updated to match the container's user (PUID/PGID)
  - Provided the user has write permissions to the directory
- If you don't want your existing directory permissions changed, mount a subdirectory instead
- The container will write files with permissions based on the UMASK, PUID, and PGID settings

Example directory setup before launching:

```shell
mkdir -p downloads/{,in}complete config
```

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

## VOD Downloads (Twitch)

StreamDL can download past broadcasts (VODs) from Twitch. Enable per-channel with the `vod` option:

```yaml
- site: twitch.tv
  channels:
  - name: day9tv
    quality: best
    vod: true
    vod_limit: 5  # Check the 5 most recent VODs (default: 10)
```

**How it works:**
- On each tick, StreamDL checks for new VODs using yt-dlp
- Downloaded VODs are tracked in a SQLite database (default `/app/data/streamdl.db`, configurable via `-data`) to avoid re-downloading
- In-progress downloads are tracked so interrupted downloads are retried after a stale threshold
- VOD files are named: `{user}_vod_{id}_{title}.mp4`
- Stream copy is used by default (no re-encoding) for fast downloads

**Docker volume:** Mount the data directory to persist the VOD tracking database across container restarts. If using the default `-data` path:

```yaml
volumes:
  - ./data:/app/data
```

**Separate output directories:** Use `-vod-out` and `-vod-move` to send VODs to a different location than live streams. If not set, VODs use the same `-out` and `-move` directories.

**Notes:**
- `vod: true` and live streaming are mutually exclusive per channel entry
- To download both live streams and VODs, add the same channel twice with different modes
- Currently supported for Twitch only

## Post-Download Script Hook

You can configure a script to run automatically after each successful download. The script is set per-site using the `post_script` field:

```yaml
- site: twitch.tv
  post_script: /scripts/transcode.sh
  channels:
  - name: kaicenat
    quality: best
```

The script receives the file path as its first argument, and additional context via environment variables:

| Variable | Description | Example |
|---|---|---|
| `STREAMDL_FILE` | Absolute path to the downloaded file | `/data/complete/user_2026-04-14.mp4` |
| `STREAMDL_USER` | Channel/user name | `kaicenat` |
| `STREAMDL_SITE` | Site domain | `twitch.tv` |
| `STREAMDL_TYPE` | Download type | `live` or `vod` |

The script runs asynchronously and will not block other downloads. If the script fails, an error is logged but StreamDL continues operating normally.

## Environment Variables

StreamDL supports configuration through environment variables for certain system-level settings.
These can be set directly in your shell or through the `.env` file.
Some of these are also available as flags to the `streamdl` command, this is a #TODO to harmonise.

| Variable             | Description                                                                                                       | Default  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| `STREAMDL_GRPC_ADDR` | The address for the gRPC server to bind to                                                                        | `server` |
| `STREAMDL_GRPC_PORT` | The port number for the gRPC server                                                                               | `50051`  |
| `TICK_TIME`          | Time interval (in seconds) between stream checks                                                                  | `60`     |
| `LOG_LEVEL`          | Logging verbosity level (DEBUG, INFO, WARN, ERROR)                                                                | `INFO`   |
| `UMASK`              | File permission mask in octal format (e.g. "022"). Controls default permissions for created files and directories | `022`    |
| `PUID`               | User ID that will own the files/directories created by the container (Docker only)                                | `1000`   |
| `PGID`               | Group ID that will own the files/directories created by the container (Docker only)                               | `1000`   |

### User ID and Group ID Configuration

The `PUID` and `PGID` environment variables allow you to control what user and group ID the container runs as:

- **Default Behavior**: If not specified, containers run as UID 1000, GID 1000
- **Runtime Switching**: These values are applied at container startup, allowing you to match your host user's UID/GID
- **Permission Matching**: Set these to match your host user's UID/GID to avoid permission issues with mounted volumes

Example `.env` configuration:

```bash
PUID=1001
PGID=1001
```

To find your current user's UID/GID on Linux/macOS:

```bash
id -u  # Shows your user ID
id -g  # Shows your group ID
```

### FFmpeg Resilience Settings

The following environment variables control FFmpeg's reconnection behavior for more resilient stream downloading:

| Variable | Description | Default |
| ------------------------------------ | -------------------------------------------------------------------------- | ------------ |
| `FFMPEG_MAX_RETRIES` | Maximum number of FFmpeg retry attempts for transient failures | `3` |
| `FFMPEG_RETRY_BASE_DELAY_SECONDS` | Base delay in seconds between FFmpeg retry attempts | `2` |
| `FFMPEG_RECONNECT_DELAY_MAX` | Maximum delay in seconds for FFmpeg to wait before reconnecting | `30` |
| `FFMPEG_RW_TIMEOUT_US` | FFmpeg read/write timeout in microseconds (30,000,000 = 30 seconds) | `30000000` |
| `FFMPEG_RECONNECT_ON_NETWORK_ERROR` | Enable FFmpeg reconnection on network errors (1=enabled, 0=disabled) | `1` |
| `FFMPEG_RECONNECT_ON_HTTP_ERROR` | Enable FFmpeg reconnection on HTTP errors (1=enabled, 0=disabled) | `1` |
| `FFMPEG_HTTP_SEEKABLE` | Enable HTTP seeking for better resilience (1=enabled, 0=disabled) | `1` |
| `FFMPEG_HTTP_PERSISTENT` | Keep HTTP connections alive (1=enabled, 0=disabled) | `1` |

These settings help prevent creating multiple small files when streams have temporary interruptions.

### Understanding UMASK

UMASK (User Mask) is a system setting that controls the default permissions for newly created files and directories.
It works by masking out (removing) permissions you don't want to grant by default.

- The UMASK value is specified in octal format (e.g. "022")
- For directories, the base permission is 0777 (rwxrwxrwx)
- For files, the base permission typically starts at 0666 (rw-rw-rw-)
- The UMASK is subtracted from these base permissions

Common UMASK values:

- `022`: Files: 644 (rw-r--r--), Directories: 755 (rwxr-xr-x)
- `027`: Files: 640 (rw-r-----), Directories: 750 (rwxr-x---)
- `077`: Files: 600 (rw-------), Directories: 700 (rwx------)

## Env File

To use the `.env` file:

1. Locate the `.env.example` file.
2. Rename it to `.env` and confirm that the variables are to your liking.
   For instance, `STREAMDL_GRPC_PORT=50051` sets the gRPC port for the StreamDL service.
3. To modify any variable, open the `.env` file, change the value, and save the file.
   For example, to change the gRPC port, you might modify the line to `STREAMDL_GRPC_PORT=50052`.
