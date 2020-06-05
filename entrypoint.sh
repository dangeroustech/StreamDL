#!/bin/sh

poetry run python streamdl.py -c config.yml -o /app/dl -m /app/out -r "$REPEAT_TIME" -l stdout -ll "$LOG_LEVEL"
