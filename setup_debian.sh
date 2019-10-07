#!/bin/bash

sudo apt-get update -y
sudo apt-get install ffmpeg -y
sudo pip install pipenv
pipenv install -e .
pipenv shell
