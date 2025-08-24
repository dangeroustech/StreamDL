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

## Install

### Docker

- Built on Docker 19.03.4
- Built on Docker-Compose 1.24.1

If you'd like to tweak individual parameters, the Dockerfile provided can be used.

Edit the Environment variables in `docker-compose.yml.example` to modify script functionality.

Otherwise, just rename it to `docker-compose.yml` and run `docker compose up -d`.

#### Directory Permissions

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

### FFmpeg Resilience Settings

The following environment variables control FFmpeg's reconnection behavior for more resilient stream downloading:

|| Variable             | Description                                                                                                       | Default  |
|| -------------------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
|| `FFMPEG_MAX_RETRIES` | Maximum number of FFmpeg retry attempts for transient failures                                                   | `5`      |
|| `FFMPEG_RETRY_BASE_DELAY_SECONDS` | Base delay in seconds between FFmpeg retry attempts                                                       | `5`      |
|| `FFMPEG_RECONNECT_DELAY_MAX` | Maximum delay in seconds for FFmpeg to wait before reconnecting                                             | `30`     |
|| `FFMPEG_RW_TIMEOUT_US` | FFmpeg read/write timeout in microseconds (30,000,000 = 30 seconds)                                             | `30000000` |
|| `FFMPEG_RECONNECT_ON_NETWORK_ERROR` | Enable FFmpeg reconnection on network errors (1=enabled, 0=disabled)                                     | `1`      |
|| `FFMPEG_RECONNECT_ON_HTTP_ERROR` | Enable FFmpeg reconnection on HTTP errors (1=enabled, 0=disabled)                                          | `1`      |
|| `FFMPEG_HTTP_SEEKABLE` | Enable HTTP seeking for better resilience (1=enabled, 0=disabled)                                           | `1`      |
|| `FFMPEG_HTTP_PERSISTENT` | Keep HTTP connections alive (1=enabled, 0=disabled)                                                          | `1`      |

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
