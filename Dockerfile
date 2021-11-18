FROM python:3.10-slim-bullseye
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apt update && apt install -y build-essential=12.9 libssl-dev=1.1.1k-1+deb11u1 libffi-dev=3.3-6 python3-dev=3.9.2-3 cargo=0.47.0-3+b1
RUN pip install poetry==1.1.11
# Copy in app files
COPY . .
# Create download directories
RUN mkdir -p /app/out
RUN mkdir -p /app/dl
# Create poetry venv
RUN poetry install
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]