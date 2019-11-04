#!/usr/bin/env python3

##TODO: Figure out what to do with pids/processes as you probably don't need both

import logging
from logging.handlers import RotatingFileHandler
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
import signal
import subprocess

# set up manager functions
mgr = Manager()
pids = mgr.dict()
processes = []
logger = logging.getLogger()


class YTDLLogger(object):
    """
    Just a class to shut YTDL up
    """
    def debug(self, msg):
        return

    def warning(self, msg):
        return

    def error(self, msg):
        return


def main(argv):
    """
    The main function that does the stuff
    """
    global logger

    # set up signal handler
    signal.signal(signal.SIGTERM, receive_signal)
    signal.signal(signal.SIGINT, receive_signal)

    # set up arg parser and arguments
    parser = argparse.ArgumentParser(prog='python streamdl.py', description='Download Streaming Video')
    parser.add_argument('-c', '--config', help='Config file to use')
    parser.add_argument('-l', '--logfile', help='Logfile to use (path defaults to working dir)')
    parser.add_argument('-ll', '--loglevel', help='Log Level to Set')
    parser.add_argument('-o', '--outdir', help='Output file location without trailing slash (defaults to working dir)')
    parser.add_argument('-r', '--repeat', help='Time to Repetitively Check Users, in Minutes')
    args = parser.parse_args()

    # check if log path is specified
    if not args.logfile:
        logfile = os.getcwd() + '/streamdl.log'
    else:
        if os.path.isdir(args.logfile):
            logfile = args.logfile + "/streamdl.log"
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
    if logfile == 'stdout':
        logger = stream_logger(log_level, log_format)
    else:
        logger = rotating_logger(logfile, log_level, log_format)

    logger.info("Starting StreamDL...")
    logger.info("Downloading to: {}".format(outdir))

    # check if config file is specified
    if args.config:
        users = config_reader(args.config)
        logger.info("Users in Config: {}".format(users))
        mass_downloader(users, outdir)

    # check if repeat is specified
    if args.repeat:
        recurse(args.repeat, outdir, config=args.config)


def recurse(repeat, outdir, **kwargs):
    """
    Main recursive function
    """
    global logger

    sleep_time = int(repeat) * 60
    logger.debug("Sleeping for {} Seconds".format(sleep_time))
    for i in range(sleep_time):
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            logger.debug("recurse thread interrupt caught...")
    # always reload config in case local changes are made
    users = config_reader(kwargs.get("config"))
    logger.info("Config: {}".format(users))
    mass_downloader(users, outdir)

    recurse(repeat, outdir, **kwargs)


# parse through users and launch downloader if necessary
def mass_downloader(config, outdir):
    """
    Handles the process spawning to download multiple things at once
    """
    global pids
    global processes
    global logger

    for url in config:
        for user in config[url]:
            # set up process for given user
            p = Process(name="{}".format(user), target=download_video, args=(url, user, outdir))
            # check for existing download
            if user in pids:
                logger.debug("Process {} Exists with PID {}".format(user, pids.get(user)))
            else:
                p.start()
                pids[user] = p.pid
                processes.append(p)
                logger.debug("Process {} Started with PID {}".format(p.name, p.pid))
                # pop pid from dict
    time.sleep(5)
    process_cleanup()


def process_cleanup():
    """
    Cleans up processes to prevent zombies and max recursion depth issues
    """
    global pids
    global processes
    global logger

    i = 0
    if len(processes) == 0:
        return

    # remove old zombie threads
    logger.debug("Cleaning Up Zombies...")
    logger.debug("Processes: {}".format(processes))
    while i < len(processes):
        if processes[i].is_alive():
            logger.debug("Process {}:{} is alive!".format(processes[i].name, processes[i].pid))
            i += 1
        else:
            logger.debug("Process {}:{} is dead!".format(processes[i].name, processes[i].pid))
            try:
                processes[i].close()
                # don't increment iterator
            except AssertionError:
                logger.debug("Some shit happened, process {} is not joinable...".format(processes[i]))
                i += 1
            try:
                logger.debug("popping: {}".format(processes[i].name))
                pids.pop(processes[i].name)
                logger.debug("Popped user {} from PIDs".format(processes[i].name))
                logger.debug("PIDs: {}".format(pids))
            except KeyError:
                logger.debug("KeyError When Popping {} From PIDs List".format(processes[i].name))
            processes.remove(processes[i])
    logger.debug("Processes after cleaning: {}".format(processes))


# do the video downloading
def download_video(url, user, outpath):
    """
    Handles downloading the individual videos
    """
    global logger

    # check if URL is valid
    try:
        request = requests.get("https://{}/{}".format(url, user), allow_redirects=False)
        # warn but don't fail on a redirect
        if request.status_code == 301:
            logger.debug("URL {}/{} Has Been Moved to: {}".format(url, user, request.headers['Location']))
        # fail on a bad status code
        if request.status_code >= 400:
            logging.warning("URL Has a Bad Status Code: {}/{}".format(url, user))
            logging.warning("Please check your config!")
            return False
    # fail on connection error
    except:
        logging.warning("Unexpected Error: {}".format(sys.exc_info()[0]))
        logging.warning("Invalid URL: {}/{}".format(url, user))
        logging.warning("Please file a bug report: https://github.com/biodrone/issues/new")
        return True

    # pass opts to YTDL
    ydl_opts = {
        'outtmpl': '{}/{}/{} - {}.%(ext)s'.format(outpath, url, user, datetime.now()),
        'quiet': True,
        'logger': YTDLLogger(),
        'postprocessor-args': '-movflags +faststart',
    }

    # try to pull video from the given user
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://{}/{}/".format(url, user)])
    except youtube_dl.utils.DownloadError:
        logger.debug("Download Error, {} is Probably Offline".format(user))
    except KeyboardInterrupt:
        logger.debug("Caught KeyBoardInterrupt...")

    return True


# read config and return users
def config_reader(config_file):
    """
    Reads the YAML config file
    """
    global logger

    # read config
    with open(config_file, 'r') as stream:
        data_loaded = yaml.safe_load(stream)

    # return the data read from config file
    return data_loaded


def rotating_logger(path, level, fmt):
    """
    Logger for writing to files
    """
    global logger

    logger = logging.getLogger("Rotating Log")
    logger.setLevel(level)

    # log rotates every 1mb for 9 times
    handler = RotatingFileHandler(path, maxBytes=1024000, backupCount=9)
    handler.setLevel(level)
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def stream_logger(level, fmt):
    """
    Logger for writing to stdout (for Docker)
    """
    global logger

    logger = logging.getLogger()
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def receive_signal(signum, frame):
    """
    Catches SIGTERM - Mainly to Address Docker Container Stops
    """
    global logger
    logger.debug('Received SIGTERM... Terminating.')
    kill_pids()
    sys.exit(0)


def kill_pids():
    """
    Kill all the PIDs, Even Currently Running Ones
    """
    global processes
    i = 0

    while i < len(processes):
        try:
            #ps = subprocess.run(
            #    ['pstree', '-p', '{}'.format(processes[i].pid)],
            #    text=True,
            #    stdout=subprocess.PIPE,
            #    check=True
            #)
            #pid = ps.stdout.lstrip("python3({})---ffmpeg(".format(processes[i].pid))
            #os.kill(pid[:-2], signal.SIGTERM)
            #os.kill(processes[i].pid, signal.SIGTERM)
            processes[i].terminate()
            i += 1
        except AssertionError:
            logger.debug("Some shit happened, process {} is not joinable...".format(processes[i]))
            i += 1


if __name__ == '__main__':
    # do the things
    main(sys.argv)
