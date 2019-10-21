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
import requests

# set up manager functions
mgr = Manager()
pids = mgr.dict()
processes = []


def main(argv):
    # set up arg parser and arguments
    parser = argparse.ArgumentParser(prog='python streamdl.py', description='Download Streaming Video')
    userspec = parser.add_mutually_exclusive_group(required=True)
    userspec.add_argument('-u', '--user', help='Chaturbate User')
    userspec.add_argument('-c', '--config', help='Config file to use')
    parser.add_argument('-l', '--logfile', help='Logfile to use (path defaults to working dir)')
    parser.add_argument('-ll', '--loglevel', help='Log Level to Set')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')
    parser.add_argument('-r', '--repeat', help='Time to Repetitively Check Users, in Minutes')
    args = parser.parse_args()

    # check if log path is specified
    if not args.logfile:
        logfile = 'streamdl.log'
    else:
        logfile = args.logfile

    if args.loglevel:
        log_level = getattr(logging, args.loglevel.upper())
    else:
        log_level = logging.INFO

    # check if output dir is specified
    if not args.outdir:
        outdir = os.getcwd() + "/media/"
    else:
        outdir = args.outdir

    # set up logging
    log_format = '%(asctime)s %(levelname)s: %(message)s'
    logging.basicConfig(filename=logfile, level=log_level, format=log_format)
    logging.info("Starting StreamDL...")
    logging.info("Downloading to: {}".format(outdir))

    # assign user if it's set
    if args.user:
        user = args.user
        logging.debug("User is: {}".format(user))
        download_video(user, outdir)

    # check if config file is specified
    if args.config:
        users = config_reader(args.config)
        logging.info("Users in Config: {}".format(users))
        mass_downloader(users, outdir)

    # check if repeat is specified
    if args.repeat:
        if args.user:
            recurse(args.repeat, outdir, user=args.user)
        if args.config:
            recurse(args.repeat, outdir, config=args.config)


def recurse(repeat, outdir, **kwargs):
    sleep_time = int(repeat) * 60
    logging.debug("Repeat Set to {}, Sleeping for {} Seconds".format(repeat, sleep_time))
    time.sleep(sleep_time)

    logging.debug("Recursing...")

    if kwargs.get("user", False):
        download_video(kwargs.get("user"), outdir)
    elif kwargs.get("config", False):
        # always reload config in case local changes are made
        users = config_reader(kwargs.get("config"))
        mass_downloader(users, outdir)
    else:
        logging.debug("Something went wrong, neither user or config were used but we're recursing....")

    recurse(repeat, outdir, **kwargs)


# parse through users and launch downloader if necessary
def mass_downloader(config, outdir):
    global pids
    global processes

    for url in config:
        for user in config[url]:
            # set up process for given user
            p = Process(name="{}".format(user), target=download_video, args=(url, user, outdir))
            # check for existing download
            if user in pids:
                logging.debug("Process {} Exists with PID {}".format(user, pids.get(user)))
            else:
                p.start()
                pids[user] = p.pid
                processes.append(p)
                logging.debug("Process {} Started with PID {}".format(p.name, p.pid))
                # pop pid from dict
                try:
                    pids.pop(user)
                    logging.debug("Popped user {} from PIDs".format(user))
                    logging.debug("PIDs: {}".format(pids))
                except KeyError:
                    logging.debug("KeyError When Popping {} From PIDs List".format(user))
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
    logging.debug("Processes after cleaning: {}".format(processes))


# read config and return users
def config_reader(config_file):

    # read config
    with open(config_file, 'r') as stream:
        data_loaded = yaml.safe_load(stream)
        logging.debug("Config: {}".format(data_loaded))

    # return the data read from config file
    return data_loaded


# do the video downloading
def download_video(url, user, outpath):
    global pids

    # check if URL is valid
    try:
        request = requests.get("https://{}/{}".format(url, user), allow_redirects=False)
        # warn but don't fail on a redirect
        if request.status_code == 301:
            logging.debug("URL {}/{} Has Been Moved to: {}".format(url, user, request.headers['Location']))
            logging.debug("Please check your config!")
        # fail on a bad status code
        if request.status_code >= 400:
            logging.warning("URL Has a Bad Status Code: {}/{}".format(url, user))
            logging.warning("Please check your config!")
            return False
    # fail on connection error
    except ConnectionError:
        logging.warning("Invalid URL: {}/{}".format(url, user))
        logging.warning("Please file a bug report: https://github.com/biodrone/issues/new/choose")
        return False

    # pass opts to YTDL
    ydl_opts = {
        'outtmpl': '{}/{}/{} - {}.%(ext)s'.format(outpath, url, user, datetime.now()),
        'quiet': True
    }

    # try to pull video from the given user
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://{}/{}/".format(url, user)])
    except youtube_dl.utils.DownloadError:
        logging.debug("{} is Offline".format(user))

    return True


if __name__ == '__main__':
    main(sys.argv)
