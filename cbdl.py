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

# set up manager functions
mgr = Manager()
pids = mgr.dict()
processes = []


def main(argv):
    # set up arg parser and arguments
    parser = argparse.ArgumentParser(usage='Download Streams From Your Favourite Nefarious Website')
    parser.add_argument('-u', '--user', help='Chaturbate User')
    parser.add_argument('-l', '--logfile', help='Logfile to use (defaults to working dir)')
    parser.add_argument('-ll', '--loglevel', help='Log Level to Set')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')
    parser.add_argument('-c', '--config', help='Config file to use')
    parser.add_argument('-r', '--repeat', help='Time to Repetitively Check Users, in Minutes')
    args = parser.parse_args()

    # check if log path is specified
    if not args.logfile:
        logfile = 'cbdl.log'
    else:
        logfile = args.logfile

    if args.loglevel:
        log_level = getattr(logging, args.loglevel.upper())
    else:
        log_level = logging.INFO

    # check if output dir is specified
    if not args.outdir:
        outdir = os.getcwd()
    else:
        outdir = args.outdir

    # set up logging
    log_format = '%(asctime)s %(levelname)s: %(message)s'
    logging.basicConfig(filename=logfile, level=log_level, format=log_format)
    logging.info("Starting CBDL...")
    logging.info("Downloading to: {}".format(outdir))

    # assign user if it's set
    # need to fix this with repeat at some point
    if args.user:
        user = args.user
        download_video(user, outdir)

    # check if config file is specified
    if args.config:
        users = config_reader(args.config)
        logging.info("Users in Config: {}".format(users))
        mass_downloader(users, outdir)

    # check if repeat is specified
    if args.repeat:
        recurse(args.repeat, args.config, outdir)


def recurse(repeat, config, outdir):
    sleep_time = int(repeat) * 60
    logging.debug("Repeat Set to {}, Sleeping for {} Seconds".format(repeat, sleep_time))
    time.sleep(sleep_time)

    logging.debug("Recursing...")

    # always reload config in case local changes are made
    users = config_reader(config)
    mass_downloader(users, outdir)

    recurse(repeat, config, outdir)


# parse through users and launch downloader if necessary
def mass_downloader(users, outdir):
    global pids
    global processes

    for user in users:
        # set up process for given user
        p = Process(name="{}".format(user), target=download_video, args=(user, outdir))
        # check for existing download
        if user in pids:
            logging.debug("Process {} Exists with PID {}".format(user, pids.get(user)))
        else:
            p.start()
            pids[user] = p.pid
            processes.append(p)
            # logging.debug("Process {} Started with PID {}".format(p.name, p.pid))
    time.sleep(5)
    process_cleanup()


def process_cleanup():
    global processes

    i = 0
    if len(processes) == 0:
        return

    # remove old zombie threads
    logging.debug("Cleaning Up Zombies...")
    logging.debug("Processes: {}".format(processes))
    while i < len(processes):
        if processes[i].is_alive():
            logging.debug("Process {}:{} is alive!".format(processes[i].name, processes[i].pid))
            i += 1
        else:
            logging.debug("Process {}:{} is dead!".format(processes[i].name, processes[i].pid))
            try:
                processes[i].close()
                # don't increment iterator
            except AssertionError:
                logging.debug("Some shit happened, process {} is not joinable...".format(processes[i]))
                i += 1
            processes.remove(processes[i])
    # logging.debug("Processes after cleaning: {}".format(processes))


# read config and return users
def config_reader(config_file):
    # read config
    with open(config_file, 'r') as stream:
        data_loaded = yaml.load(stream, Loader=yaml.BaseLoader)

    # return the data read from config file
    return data_loaded['users']


# do the video downloading
def download_video(user, outpath):
    global pids

    # pass opts to YTDL
    ydl_opts = {
        'outtmpl': '{}/{} - {}.%(ext)s'.format(outpath, user, datetime.now()),
        'quiet': True
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
        logging.debug("Popped user {} from PIDs".format(user))
        logging.debug("PIDs: {}".format(pids))
    except KeyError:
        logging.debug("KeyError When Popping {} From PIDs List".format(user))
    
    return


if __name__ == '__main__':
    main(sys.argv)
