FROM python:3.9.5-alpine
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apk update && apk upgrade
RUN apk add --no-cache build-base git ffmpeg openssl-dev libffi-dev cargo
RUN pip install poetry
# Copy in app files
ADD . .
# Create out directories
RUN mkdir /app/out
# Create poetry venv
RUN poetry install
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
