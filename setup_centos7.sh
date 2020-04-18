#!/bin/bash

sudo yum update -y
sudo yum install centos-release-scl -y
sudo yum update -y
sudo yum install ffmpeg rh-python38 -y
sudo yum groupinstall 'Development Tools' -y
scl enable rh-python36 bash
sudo pip install pipenv
pipenv install -e .
