FROM ubuntu:latest
WORKDIR /app
# Create in and out Directories
RUN mkdir /app/in
RUN mkdir /app/out
# Install necessary software
RUN apt-get update && apt-get upgrade -y
RUN apt-get install git python3 python3-pip ffmpeg -y
RUN pip3 install pipenv
# Copy in app files
ADD cbdl.py /app
ADD config.yml.example /app
ADD setup.py /app
ADD Pipfile /app
ADD Pipfile.lock /app
# Random Build Tests
RUN mv /app/config.yml.example /app/config.yml
RUN pipenv install -e .
RUN pipenv shell
RUN python3 cbdl.py --help