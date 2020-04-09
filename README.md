# StreamDL

[![Build Status](https://travis-ci.com/dangerous-tech/StreamDL.svg?branch=master)](https://travis-ci.com/dangerous-tech/StreamDL)

Monitor and Download Streams from a Variety of Websites

## Why Does This Exist?

Because there are certain streaming websites that don't store historic VODs of their livestreams. This is sad. As a nerd, you probably have terabytes of storage somewhere, right? Why not get some use out of it? Archivists everywhere, rejoice!

## Usage

```shell
  usage: Monitor and Download Streams from a Variety of Websites

  optional arguments:
  -h,               --help      show this help message and exit
  -l    LOGPATH,    --logpath   LOGPATH
                                Logfile to use (defaults to working dir)
  -ll   LOGLEVEL,   --loglevel  Loglevel to use (supports DEBUG, INFO, etc)
  -o    OUTDIR,     --outdir    OUTDIR
                                Output file location without trailing slash
                                (defaults to working dir)
  -c    CONFIG,     --config    CONFIG
                                Config file to use
  -r    REPEAT,     --repeat    REPEAT
                                Time to Repetitively Check Users, in Minutes
```

## Requirements

### Docker
- Built on Docker 19.03.4
- Built on Docker-Compose 1.24.1

### Bare Metal

- Python 3.7
- ffmpeg
- pipenv (`pip install pipenv` *or* `pip3 install pipenv` *depending on your system*)

## Install

### Docker

If you'd like to tweak individual parameters, the Dockerfile provided can be used. 

Otherwise, just run `docker-compose up -d`

Edit the Environment variables in `docker-compose.yml.example` to modify script functionality. 

Logs are piped to stdout by default so that `docker-compose logs` works. *If you know what you're doing, you can change this value in `entrypoint.sh`. Make sure to rebuild the container with `docker-compose build` after editing this.*

### Bare Metal

*This example assumes `python --version` returns something above Python 3.6 and you have made a config.yml file based on the `config.yml.example` provided in the repo.*

- `pipenv install -e .`

- `pipenv run python streamdl.py -c config.yml -r 5`

Alternatively, use the shell scripts provided depending on your environment:

- `./setup_centos.sh`

OR

- `./setup_debian.sh`

## Config File

Basic YAML format. See config.yaml.example for a couple of test sites.

```yaml
twitch.tv:
- kaypealol
- day9tv
mixer.com:
- ninja
```
