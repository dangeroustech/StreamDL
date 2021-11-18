FROM python:3.9-slim
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
# RUN apk update && apk upgrade
# RUN apk add --no-cache build-base git ffmpeg openssl-dev libffi-dev cargo
RUN pip install poetry==1.1.7
# Copy in app files
COPY . .
# Create download directories
RUN mkdir -p /app/out
RUN mkdir -p /app/dl
# Create poetry venv
RUN poetry install
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
