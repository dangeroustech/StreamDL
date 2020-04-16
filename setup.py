#!/usr/bin/python

from setuptools import setup

setup(
    name="StreamDL",
    version="1.2.2",
    description="Monitor and Download Streams from a Variety of Websites",
    author="biodrone",
    install_requires=['youtube_dl==2019.11.22', 'PyYAML==5.3.1', 'requests==2.22'],
)
