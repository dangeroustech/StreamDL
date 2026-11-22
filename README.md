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

Flags accept one or two leading dashes (`-config` or `--config`).

| Flag           | Description                                                  | Default           |
| -------------- | ------------------------------------------------------------ | ----------------- |
| `-h`, `--help` | Show this help message and exit                              | -                 |
| `-config`      | Location of config file (full path inc filename)             | `config.yml`      |
| `-out`         | Folder for in-progress recordings; must be set to a usable folder | none (the image uses `/app/dl`) |
| `-move`        | Folder finished recordings are moved to; must be set to a usable folder | none (the image uses `/app/out`) |
| `-time`        | Time interval to check for streams (in seconds)              | `60`              |
| `-batch`       | Time between URL checks (seconds): increase for rate limiting | `5`               |
| `-subfolder`   | Add streams to a subfolder with the channel name             | `false`           |
| `-log-level`   | Set logging level (debug, info, warn, error, etc)            | `info`            |
| `-log-dest`    | Primary log destination: `file`, `stdout`, or `both`         | `file`            |
| `-log-file`    | Log file path (used when `-log-dest` is `file` or `both`)    | `<data>/streamdl.log` |
| `-data`        | Directory for persistent data (VOD tracking database + default log) | `/app/data`  |
| `-vod-out`     | Output location for VOD downloads (defaults to `-out`)       | Same as `-out`    |
| `-vod-move`    | Move location for completed VOD downloads (defaults to `-move`) | Same as `-move` |

## Install

### Docker

StreamDL runs as a single container, `dangeroustech/streamdl:client_stable`.

Copy `docker-compose.yml.example` to `docker-compose.yml`, adjust the volumes and `.env`, and run `docker compose up -d`. The container answers health checks on port 8080 (`/health`).

### Upgrading from v3

v4 replaces the separate `server` and `client` containers with one container. Your config, environment variables, folders and VOD database carry over (the two gRPC variables become unused).

1. Pull the new image: `docker compose pull`.
2. Delete the `server` service, and the client's `depends_on: server`, from your `docker-compose.yml`.
3. Remove `STREAMDL_GRPC_ADDR` and `STREAMDL_GRPC_PORT` from `.env`. They're ignored now.
4. Run `docker compose up -d --remove-orphans`.

If you skip step 2, the old server container keeps running, but nothing talks to it.

On TrueNAS, Portainer or another UI that manages the compose file for you, edit the app's YAML instead: delete the `server` service (and the `depends_on`), then redeploy with the image re-pulled.

Some behaviour changed on purpose in v4:

- Twitch live recordings skip Twitch's ads (see [Twitch Ad-Free Recording](#twitch-ad-free-recording)). Set `TWITCH_ADFREE=false` to record them with the ads, as v3 did (leave `TWITCH_OAUTH_TOKEN` unset too, since lookups still send it).
- Notices from yt-dlp no longer end with its "please report this issue" suffix.
- A long VOD download is no longer started a second time while the first is still running.
- Stream tokens and signatures are more thoroughly redacted from the logs.
- `-time` (and `TICK_TIME`) must be greater than 0.

#### Security Best Practices

StreamDL containers drop privileges at runtime by switching to a non-root user:

- **Default Runtime User**: The entrypoint creates/uses a `streamdl` user with UID 1000 and GID 1000 unless `PUID`/`PGID` override them
- **Runtime User Switching**: Supports dynamic UID/GID switching via `PUID`/`PGID` environment variables
- **User Tools**: Uses `gosu` to switch to the runtime user and `tini` as PID 1
- **Directory Permissions**: The entrypoint creates the directories it manages at startup

##### Directory Permissions

When using Docker, be aware of the following:

- It's recommended to create the download directories **before** running the container
- All directories mounted in Docker will have their permissions updated to match the container's user (PUID/PGID)
  - Provided the user has write permissions to the directory
- If you don't want your existing directory permissions changed, mount a subdirectory instead
- Files and folders the container writes are owned by PUID/PGID; see [Understanding UMASK](#understanding-umask) for their permissions

Example directory setup before launching:

```shell
mkdir -p downloads/{,in}complete config data
```

### Intel Quick Sync / `/dev/dri` passthrough

StreamDL can optionally receive the host Intel graphics device so hardware encode/decode is possible **when FFmpeg supports it**.

**Important limitations today**

- The StreamDL image uses a static FFmpeg build (`mwader/static-ffmpeg`), which does **not** include Quick Sync (QSV) or VAAPI. Passing `/dev/dri` into that image alone will not accelerate encodes.
- Most StreamDL downloads remux with stream copy (`-c copy` for VODs; optional via `FFMPEG_STREAM_COPY` for live). Remuxing does not use the GPU. Quick Sync only helps when something **re-encodes** (in-process via `FFMPEG_EXTRA_*`, or a `post_script` transcoder).
- A QSV/VAAPI-capable image is tracked in #611; first-class hwaccel presets in #612.

**Enable device access (opt-in)**

1. Confirm the host has a render node, e.g. `ls -l /dev/dri`.
2. Note the `video` / `render` group IDs (they vary by distro):
   ```shell
   getent group video render
   stat -c '%g' /dev/dri/renderD128
   ```
3. In `docker-compose.yml`, uncomment the `devices:` / `group_add:` block from `docker-compose.yml.example` and replace the example GIDs with yours.
4. Keep `PUID`/`PGID` as usual for download file ownership; `group_add` is separate and only grants DRM device access.

Example (GIDs illustrative only):

```yaml
devices:
  - /dev/dri:/dev/dri
group_add:
  - "44"   # video
  - "992"  # render
```

On TrueNAS / Kubernetes-style apps, map the same device and supplemental groups through the UI or runtime equivalent of Docker `devices` + `group_add`.

### Logging

StreamDL can send full application logs to a file, container stdout, or both:

| `LOG_DEST` / `-log-dest` | Primary logs | Container stdout (`docker compose logs`) |
| ------------------------ | ------------ | ---------------------------------------- |
| `file` (default)         | `<data>/streamdl.log` | Active Downloads summary each tick only |
| `stdout`                 | stdout       | Full logs (legacy-style)                 |
| `both`                   | file + stdout | Full logs, and the same content in the log file |

Override the file path with `LOG_FILE` / `-log-file` when using `file` or `both`. Mount `/app/data` (see `docker-compose.yml.example`) so the default log file and VOD database persist on the host.

### Bare Metal

Requirements:

- Python 3.14 or newer
- ffmpeg
- uv (`pip install uv` or `pip3 install uv` depending on your system)
- deno (optional; yt-dlp uses it for YouTube)

#### Example Run

```shell
# Clone the repository
git clone https://github.com/dangeroustech/streamdl && cd streamdl

# Create your config from the example
cp config/config.yml.example config/config.yml

# Run StreamDL (uv installs the dependencies into .venv on first run)
uv run --no-dev streamdl -config ./config/config.yml -out ./downloads/incomplete -move ./downloads/complete -data ./data -time 300
```

## Config File

Basic YAML format. See `config/config.yml.example` for a couple of test sites.

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

You can configure a script to run automatically after each successful download — for both live streams and VODs. The script is set per-site using the `post_script` field:

```yaml
- site: twitch.tv
  post_script: /scripts/transcode.sh
  channels:
  - name: kaicenat
    quality: best
```

The script must exist and be executable (`chmod +x /scripts/transcode.sh`). It receives the file path as its first argument, and additional context via environment variables:

| Variable | Description | Example |
|---|---|---|
| `STREAMDL_FILE` | Path to the downloaded file | `/data/complete/user_2026-04-14.mp4` |
| `STREAMDL_USER` | Channel/user name | `kaicenat` |
| `STREAMDL_SITE` | Site domain | `twitch.tv` |
| `STREAMDL_TYPE` | Download type | `live` or `vod` |

The script runs asynchronously and will not block other downloads. If the script fails or exceeds the timeout, an error is logged but StreamDL continues operating normally. Use `STREAMDL_POST_SCRIPT_TIMEOUT` (seconds, default `1800`) to cap how long a hook may run.

When StreamDL stops, it waits for running hooks to finish (a second stop signal makes it exit at once instead). Docker only waits 10 seconds before killing the container, and any unfinished hook dies with it. If your hooks run longer (a transcode, say), raise the grace period on your StreamDL service in `docker-compose.yml` (`client` if you kept the v3 name):

```yaml
services:
  streamdl:
    stop_grace_period: 30m
```

**Docker:** Mount your script directory into the container and point `post_script` at the in-container path:

```yaml
volumes:
  - ./scripts:/scripts:ro
```

## Tick Notices

At the end of each check cycle, StreamDL logs a wait line followed by any actionable notices collected during that tick:

```text
Waiting 60s until next check...
--- notices ---
[day9tv] Requested format '1080p60' unavailable; using default selection
```

Notices cover things like quality fallbacks, rate-limit skips, and download failures. Each notice is shown at most once per channel until the channel goes offline (live) or the condition clears, so repeated warnings within a tick are deduplicated.

## Environment Variables

StreamDL supports configuration through environment variables for certain system-level settings.
These can be set directly in your shell or through the `.env` file.
Some of these are also available as flags to the `streamdl` command, this is a #TODO to harmonise.

| Variable             | Description                                                                                                       | Default  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| `TICK_TIME`          | Time interval (in seconds) between stream checks                                                                  | `60`     |
| `LOG_LEVEL`          | Logging verbosity level (DEBUG, INFO, WARN, ERROR)                                                                | `INFO`   |
| `LOG_DEST`           | Primary log destination: `file`, `stdout`, or `both`                                                              | `file`   |
| `LOG_FILE`           | Log file path when `LOG_DEST` is `file` or `both`                                                                 | `/app/data/streamdl.log` |
| `UMASK`              | File permission mask in octal format (e.g. "022"). Applied to folders StreamDL creates and to files it copies across filesystems (see below) | `022`    |
| `PUID`               | User ID that will own the files/directories created by the container (Docker only)                                | `1000`   |
| `PGID`               | Group ID that will own the files/directories created by the container (Docker only)                               | `1000`   |
| `STREAMDL_POST_SCRIPT_TIMEOUT` | Maximum seconds a post-download hook may run before being killed                          | `1800`   |

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

### FFmpeg Settings

These apply to live recordings (see [Twitch Ad-Free Recording](#twitch-ad-free-recording) for the ones that don't apply there). VODs are always stream-copied and ignore them.

| Variable | Description | Default |
| --- | --- | --- |
| `FFMPEG_MAX_RETRIES` | Retries after FFmpeg exits with an error or records nothing, counting failures in a row | `3` |
| `FFMPEG_RETRY_BASE_DELAY_SECONDS` | Delay before the first retry; doubles on each retry | `2` |
| `FFMPEG_RW_TIMEOUT_US` | Network read/write timeout in microseconds | `15000000` (15s) |
| `FFMPEG_RECONNECT` | Reconnect dropped single-input streams (`0` or `false` turns it off) | on |
| `FFMPEG_RECONNECT_DELAY_MAX` | Longest wait between reconnect attempts, in seconds | `15` |
| `FFMPEG_PROTOCOL_WHITELIST` | Value for FFmpeg's `-protocol_whitelist` | unset |
| `FFMPEG_USER_AGENT` | User agent FFmpeg sends | FFmpeg's default |
| `FFMPEG_STREAM_COPY` | `1` or `true` copies live streams instead of re-encoding them | off |
| `FFMPEG_EXTRA_INPUT_OPTS` | Extra FFmpeg options placed before the input | unset |
| `FFMPEG_EXTRA_OUTPUT_OPTS` | Extra FFmpeg options placed before the output file | unset |

Retries fetch a fresh stream URL each time, so a recording survives expired stream tokens.

### Dropped Streams

Live streams sometimes stall for a few seconds, and FFmpeg can take a stall as the end of the stream. When FFmpeg stops, StreamDL keeps checking the channel for `RECONNECT_WINDOW` seconds. If the stream comes back, it records another part (`<name>_part2.mp4`, `_part3.mp4`, …) next to the first one in the download directory, and the channel gets a notice such as `[alice] Stream came back after 10s; recording part 2`. The few seconds missed while checking are a jump in the recording.

When the channel stays offline for the whole window, StreamDL joins the parts into one file with the recording's usual name. The join copies the video and audio without re-encoding, so it takes about as long as copying the file. The joined copy is written next to the parts, so StreamDL first checks that the download directory has room for it (the parts' size plus 5%). Then it moves the file and runs your post-script once. If the parts don't match (the streamer changed resolution, say), there isn't enough room, or the join fails, StreamDL keeps the parts, moves each one, runs the post-script for each, and says why in a notice.

When FFmpeg fails (exits with an error, or stops without recording anything) it is retried as before (`FFMPEG_MAX_RETRIES`, counting failures in a row). Each retry also writes a new part, so nothing already recorded is overwritten. Empty parts are deleted, and if only one part recorded anything, it keeps the recording's usual name.

If StreamDL is stopped while recording, waiting for a stream to come back, or joining, the parts stay in the download directory as they are, and nothing is joined or moved.

| Variable | Description | Default |
| --- | --- | --- |
| `RECONNECT_WINDOW` | Seconds to keep checking a channel after FFmpeg stops. `0` finishes the recording at once, as before | `30` |
| `RECONNECT_INTERVAL` | Seconds between those checks (at least 1) | `5` |

These aren't `FFMPEG_RECONNECT` and `FFMPEG_RECONNECT_DELAY_MAX`, which let FFmpeg reconnect on its own while it's still running; the window starts only once FFmpeg has stopped.

If you use `-t` in `FFMPEG_EXTRA_OUTPUT_OPTS` to split recordings into fixed-length files, set `RECONNECT_WINDOW=0`. Otherwise each split looks like a drop, and the pieces are joined back together.

### Twitch Ad-Free Recording

Live Twitch recordings go through streamlink, which drops Twitch's ad segments before FFmpeg sees them. Where an ad ran, the recording skips ahead, so expect a short jump instead of an ad. Ad breaks appear as notices, such as `[alice] Skipping a 30s ad break`; a repeat of the same length is shown once per recording. VODs and other sites record as before, except that Twitch VOD lookups also send `TWITCH_OAUTH_TOKEN` when it is set (so sub-only VODs can be downloaded, and a rejected token stops VOD downloads too).

| Variable | Description | Default |
| --- | --- | --- |
| `TWITCH_ADFREE` | `0` or `false` records Twitch directly with FFmpeg, ads included, as v3 did; any other value leaves it on | on |
| `TWITCH_OAUTH_TOKEN` | Your Twitch login token. With Twitch Turbo or a sub to the channel, Twitch sends no ads, so there are no jumps, and sub-only streams can be recorded | unset |

To find your token, log in to twitch.tv in a browser, open the developer tools and copy the value of the `auth-token` cookie (Application → Cookies in Chrome, Storage → Cookies in Firefox). Paste the bare value: surrounding quotes are tolerated, but a token with spaces or non-ASCII characters is ignored with a warning. Treat it like a password: it gives access to your Twitch account. StreamDL never logs it and hands it to streamlink through a private temporary file, so the temporary folder (`/tmp`, or `TMPDIR`) must be writable. If Twitch rejects it, the channel gets a `Twitch rejected TWITCH_OAUTH_TOKEN` notice.

FFmpeg reads from streamlink rather than the network here, so `FFMPEG_RW_TIMEOUT_US`, `FFMPEG_RECONNECT`, `FFMPEG_RECONNECT_DELAY_MAX`, `FFMPEG_USER_AGENT`, `FFMPEG_PROTOCOL_WHITELIST` and `FFMPEG_EXTRA_INPUT_OPTS` don't apply to ad-free Twitch recordings. The other FFmpeg settings do.

If streamlink loses the stream mid-broadcast, FFmpeg finishes the current part, and StreamDL waits for the stream to come back as described in [Dropped Streams](#dropped-streams).

### Understanding UMASK

A umask lists the permissions to remove from new files and folders, in octal (e.g. "022").
StreamDL's `UMASK` setting does not change the process umask, so it only applies in two places:

- **Folders StreamDL creates** (the output and move folders, and per-channel subfolders) get 0777 minus `UMASK`,
  e.g. 755 (rwxr-xr-x) with `022`. Folders that already exist are left alone; in the container the entrypoint creates
  `/app/dl`, `/app/out` and `/app/data` itself, so there it is the per-channel subfolders that get `UMASK`.
- **Recordings moved across filesystems** (e.g. from a local `/app/dl` to a NAS-backed `/app/out`) are copied, and the
  copy keeps the original file's permissions with `UMASK` also removed.

The recordings themselves are created by FFmpeg with the process umask (the container default, normally 022, which gives
644), and a move within one filesystem keeps those permissions. So `UMASK` can make recordings more restrictive after a
cross-filesystem move, but it can't make them more permissive than that.

Common UMASK values for folders:

- `022`: 755 (rwxr-xr-x)
- `027`: 750 (rwxr-x---)
- `077`: 700 (rwx------)

## Env File

To use the `.env` file:

1. Locate the `.env.example` file.
2. Rename it to `.env` and confirm that the variables are to your liking.
   For instance, `TICK_TIME=60` checks your channels every 60 seconds.
3. To modify any variable, open the `.env` file, change the value, and save the file.
   For example, to check every five minutes, change the line to `TICK_TIME=300`.
