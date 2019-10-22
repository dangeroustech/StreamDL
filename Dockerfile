FROM ubuntu:latest
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Create out directory
RUN mkdir /app/out
# Install necessary software
RUN apt-get update && apt-get upgrade -y
RUN apt-get install git python3.7 python3-pip ffmpeg -y
RUN pip3 install pipenv
# Copy in app files
ADD streamdl.py /app
ADD config.yml.example /app
ADD setup.py /app
ADD Pipfile /app
ADD Pipfile.lock /app
# Create pipenv
RUN pipenv install -e .
ENTRYPOINT [ "entrypoint.sh" ]
