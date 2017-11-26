#!/usr/bin/python

import logging
import argparse
import sys

LOG_LEVEL = logging.DEBUG
FORMAT = '%(asctime)s %(levelname)s: %(message)s'


def main(argv):
    parser = argparse.ArgumentParser(usage='Download the Current Stream by a Chaturbate User')
    parser.add_argument('-u', '--user', help='Chaturbate Username', required=True)
    parser.add_argument('-l', '--logfile', help='Logfile to use (defaults to working dir)')

    args = parser.parse_args()

    if not args.logpath:
        logfile = 'chaturdownload.log'
    else:
        logfile = args.logpath
    user = args.user
    logging.basicConfig(filename=logfile, level=LOG_LEVEL, format=FORMAT)
    logging.debug("Starting ChaturDownload...")
    logging.debug("Using User: {}".format(user))


def get_stream(user):
    logging.debug("Getting Stream...")


def download_video(stream):
    logging.debug("Downloading Video...")

main(sys.argv)
