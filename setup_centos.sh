#!/bin/bash

sudo yum update -y
sudo yum install ffmpeg -y
sudo pip install pipenv
pipenv install -e .
pipenv shell
