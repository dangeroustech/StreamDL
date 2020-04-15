FROM python:3.7-alpine
WORKDIR /app
ARG TRAVIS_BRANCH=$TRAVIS_BRANCH
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apk update && apk upgrade
RUN apk add --no-cache git ffmpeg
RUN pip3 install pipenv
# Copy in app files
RUN git clone https://github.com/biodrone/StreamDL /app
# Checkout staging if required
RUN if [ "${TRAVIS_BRANCH}" != "master" ]; then git checkout "${TRAVIS_BRANCH}"; fi
# Create out directory
RUN mkdir /app/out
# Create pipenv
RUN pipenv install -e .
ENTRYPOINT ["pipenv", "run", "python3", "streamdl.py", "-o", "/app/out", "-c", "config.yml", "-r", "$REPEAT_TIME", "-l", "stdout", "-ll", "$LOG_LEVEL"]
