#!/usr/bin/python

from setuptools import setup

setup(
    name="StreamDL",
    version="1.0.0",
    description="Monitor and Download Streams from a Variety of Websites",
    author="biodrone",
    install_requires=['youtube_dl==2019.11.05', 'PyYAML==5.1.2', 'requests==2.22'],
)
