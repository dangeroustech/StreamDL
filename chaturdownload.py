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

LOG_LEVEL = logging.DEBUG
FORMAT = '%(asctime)s %(levelname)s: %(message)s'
mgr = Manager()
pids = mgr.dict()


def main(argv):
    parser = argparse.ArgumentParser(usage='Download the Current Stream by a Chaturbate User')
    parser.add_argument('-u', '--user', help='Chaturbate User')
    parser.add_argument('-l', '--logpath', help='Logfile to use (defaults to working dir)')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')
    parser.add_argument('-c', '--config', help='Config file to use')
    parser.add_argument('-r', '--repeat', help='Time to Repetitively Check Users, in Minutes')

    args = parser.parse_args()

    if not args.logpath:
        logfile = 'chaturdownload.log'
    else:
        logfile = args.logpath
    if not args.outdir:
        outdir = os.getcwd()
    else:
        outdir = args.outdir
    user = args.user

    logging.basicConfig(filename=logfile, level=LOG_LEVEL, format=FORMAT)
    logging.debug("Starting ChaturDownload...")
    logging.debug("Downloading to: {}".format(outdir))

    if args.config:
        users = config_reader(args.config)
        logging.debug("Users in Config: {}".format(users))
        mass_downloader(users, outdir, pids)
    else:
        download_video(user, outdir)

    # REMOVE BEFORE COMMIT
    time.sleep(5)
    logging.debug("PIDS List After Downloader Run: {}".format(str(pids)))
    # REMOVE BEFORE COMMIT

    if args.repeat:
        logging.debug("Repeat Set to {}, Sleeping for {} Seconds".format(args.repeat, int(args.repeat)*60))
        time.sleep(int(args.repeat)*60)
        logging.debug("Restarting Main Function")
        main(sys.argv)


def mass_downloader(users, outdir, pids):
    for user in users:
        p = Process(name="{}".format(user), target=download_video, args=(user, outdir, pids))
        if user in pids:
            logging.debug("Process {} Exists with PID {}".format(user, pids.get(user)))
        else:
            p.start()
            pids[user] = p.pid
            logging.debug("Process {} Started with PID {}".format(p.name, p.pid))


def config_reader(config_file):

    with open(config_file, 'r') as stream:
        data_loaded = yaml.load(stream)

    return data_loaded['users']


def download_video(user, outpath, pids):
    ydl_opts = {
        'outtmpl': '{}/{} - {}.%(ext)s'.format(outpath, user, datetime.now())
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.chaturbate.com/{}/".format(user)])
    except youtube_dl.utils.DownloadError:
        logging.debug("{} is Offline".format(user))

    try:
        pids.pop(user)
    except KeyError:
        logging.debug("KeyError When Popping {} From PIDS List".format(user))
    return


if __name__ == '__main__':
    main(sys.argv)
