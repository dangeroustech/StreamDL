#!/usr/bin/python

import logging
import argparse
import sys
import re
from bs4 import BeautifulSoup as bs
import requests
import time
import os

LOG_LEVEL = logging.DEBUG
FORMAT = '%(asctime)s %(levelname)s: %(message)s'


def main(argv):
    parser = argparse.ArgumentParser(usage='Download the Current Stream by a Chaturbate User')
    parser.add_argument('-u', '--user', help='Chaturbate Username', required=True)
    parser.add_argument('-l', '--logpath', help='Logfile to use (defaults to working dir)')
    parser.add_argument('-o', '--outdir', help='Output file location (defaults to working dir)')

    args = parser.parse_args()

    if not args.logpath:
        logfile = 'chaturdownload.log'
    else:
        logfile = args.logpath
    if not args.outdir:
        os.chdir(os.path.dirname(__file__))
        outDir = os.getcwd()
    else:
        outDir = args.outdir
    user = args.user

    logging.basicConfig(filename=logfile, level=LOG_LEVEL, format=FORMAT)
    logging.debug("Starting ChaturDownload...")
    logging.debug("Using User: {}".format(user))

    stream, title = get_stream(user)
    logging.debug("Stream URL Received: {}".format(stream))
    logging.debug("Stream Title Received: {}".format(title))

    download_video(stream, outDir, title)


def get_stream(user):
    logging.debug("FUNCTION: Getting Stream...")
    regex = re.compile('https:..edge.+?m3u8')
    URL = "https://chaturbate.com/{}".format(user)
    r = requests.get(URL)
    soup = bs(r.text, 'html.parser')
    stream = str(soup.find_all(string=regex))
    stream_url = re.search(regex, stream).group()
    room_title = ""

    for string in soup.strings:
        if "default_subject" in string:
            room_title = re.search('default_subject: \"(.+)\"', string).group().lstrip("default_subject: \"").rstrip("\"")

    room_title = room_title.replace("%20", "_").replace("%23", "#")

    return stream_url, room_title


def download_video(stream, outpath, filename):
    logging.debug("FUNCTION: Downloading Video...")


main(sys.argv)
