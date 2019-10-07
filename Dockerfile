FROM ubuntu:latest
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Create in and out Directories
RUN mkdir /app/in
RUN mkdir /app/out
# Install necessary software
RUN apt-get update && apt-get upgrade -y
RUN apt-get install git python3.7 python3-pip ffmpeg -y
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
ENTRYPOINT [ "pipenv", "run", "python3", "cbdl.py", "-c", "config.yml", "-r", "5" ]
