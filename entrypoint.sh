#!/bin.sh

poetry run python streamdl.py -o /app/out -c config.yml -r "$REPEAT_TIME" -l stdout -ll "$LOG_LEVEL"
