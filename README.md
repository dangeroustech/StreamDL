[![Build Status](https://travis-ci.org/biodrone/StreamDL.svg?branch=master)](https://travis-ci.org/biodrone/StreamDL)

# StreamDL

```shell
  usage: Monitor and Download Streams from a Variety of Websites

  optional arguments:
  -h,               --help      show this help message and exit
  -u    USER,       --user      USER
                                Streaming Site User
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

- Python 3.7
- ffmpeg
- pipenv (`pip install pipenv`)

## Install

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
twitch.tv
- kaypealol
- day9tv
youtube
- UC4w1YQAJMWOz4qtxinq55LQ
```

*YouTube Caveat: make sure that youtube.com/channel/videos resolves to the right place.*
*Channel renaming hides that on the main page.*
