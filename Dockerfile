FROM python:3.8-alpine
WORKDIR /app
ARG TRAVIS_BRANCH=$TRAVIS_BRANCH
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apk update && apk upgrade
RUN apk add --no-cache build-base git ffmpeg
RUN pip3 install poetry
# Copy in app files
RUN git clone https://github.com/biodrone/StreamDL /app
# Checkout staging if required
RUN if [ "${TRAVIS_BRANCH}" = "staging" ]; then git checkout staging; fi
# Create out directory
RUN mkdir /app/out
# Create pipenv
RUN poetry install
ENTRYPOINT ["poetry", "run", "python3", "streamdl.py", "-o", "/app/out", "-c", "config.yml", "-r", "$REPEAT_TIME", "-l", "stdout", "-ll", "$LOG_LEVEL"]
