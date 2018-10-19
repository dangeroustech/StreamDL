#!/usr/bin/python

import logging
import argparse
import sys
import os
import youtube_dl
from datetime import datetime

LOG_LEVEL = logging.DEBUG
FORMAT = '%(asctime)s %(levelname)s: %(message)s'


def main(argv):
    parser = argparse.ArgumentParser(usage='Download the Current Stream by a Chaturbate User')
    parser.add_argument('-u', '--user', help='Chaturbate User', required=True)
    parser.add_argument('-l', '--logpath', help='Logfile to use (defaults to working dir)')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')

    args = parser.parse_args()

    if not args.logpath:
        logfile = 'chaturdownload.log'
    else:
        logfile = args.logpath
    if not args.outdir:
        outDir = os.getcwd()
    else:
        outDir = args.outdir
    user = args.user

    logging.basicConfig(filename=logfile, level=LOG_LEVEL, format=FORMAT)
    logging.debug("Starting ChaturDownload...")
    logging.debug("Downloading From User: {}".format(user))
    logging.debug("Downloading to: {}".format(outDir))

    download_video(user, outDir)


def download_video(user, outpath):
    logging.debug("FUNCTION: Downloading Video...")

    ydl_opts = {}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download(["https://www.chaturbate.com/{}/ -o {}/{} - {}.%(ext)s".format(user, outpath, user, datetime.now())])


main(sys.argv)
