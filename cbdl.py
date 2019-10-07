#!/usr/bin/python

import logging
import argparse
import sys
import os
import youtube_dl
from datetime import datetime
import yaml
from multiprocessing import Manager
from multiprocessing import Process
import time

# global vars to control logging level and format
LOG_LEVEL = logging.DEBUG
FORMAT = '%(asctime)s %(levelname)s: %(message)s'

# set up manager functions
mgr = Manager()
pids = mgr.dict()


def main(argv):
    # set up arg parser and arguments
    parser = argparse.ArgumentParser(usage='Download Streams From Your Favourite Nefarious Website')
    parser.add_argument('-u', '--user', help='Chaturbate User')
    parser.add_argument('-l', '--logfile', help='Logfile to use (defaults to working dir)')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')
    parser.add_argument('-c', '--config', help='Config file to use')
    parser.add_argument('-r', '--repeat', help='Time to Repetitively Check Users, in Minutes')
    args = parser.parse_args()

    # check if log path is specified
    if not args.logfile:
        logfile = 'cbdl.log'
    else:
        logfile = args.logfile

    # check if output dir is specified
    if not args.outdir:
        outdir = os.getcwd()
    else:
        outdir = args.outdir

    user = args.user

    # set up logging
    logging.basicConfig(filename=logfile, level=LOG_LEVEL, format=FORMAT)
    logging.debug("Starting CBDL...")
    logging.debug("Downloading to: {}".format(outdir))

    # check if config file is specified
    if args.config:
        users = config_reader(args.config)
        logging.debug("Users in Config: {}".format(users))
        mass_downloader(users, outdir, pids)
    else:
        download_video(user, outdir)

    time.sleep(5)
    logging.debug("Live Users: {}".format(users))

    # check if repeat is specified
    if args.repeat:
        logging.debug("Repeat Set to {}, Sleeping for {} Seconds".format(args.repeat, int(args.repeat)*60))
        time.sleep(int(args.repeat)*60)
        logging.debug("Restarting Main Function")
        main(sys.argv)


# parse through users and launch downloader if necessary
def mass_downloader(users, outdir, pids):
    for user in users:
        # set up process for given user
        p = Process(name="{}".format(user), target=download_video, args=(user, outdir, pids))
        # check for existing download
        if user in pids:
            logging.debug("Process {} Exists with PID {}".format(user, pids.get(user)))
        else:
            p.start()
            pids[user] = p.pid
            logging.debug("Process {} Started with PID {}".format(p.name, p.pid))


# read config and return users
def config_reader(config_file):
    # read config
    with open(config_file, 'r') as stream:
        data_loaded = yaml.load(stream)

    # return the data reead from config file
    return data_loaded['users']


# do the video downloading
def download_video(user, outpath, pids):
    # pass opts to YTDL
    ydl_opts = {
        'outtmpl': '{}/{} - {}.%(ext)s'.format(outpath, user, datetime.now())
    }

    # try to pull video from the given user
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.chaturbate.com/{}/".format(user)])
    except youtube_dl.utils.DownloadError:
        logging.debug("{} is Offline".format(user))

    # pop pid from dict
    try:
        pids.pop(user)
    except KeyError:
        logging.debug("KeyError When Popping {} From PIDS List".format(user))
    
    return


if __name__ == '__main__':
    main(sys.argv)
