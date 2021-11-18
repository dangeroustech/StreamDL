FROM python:3.10-slim
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apt update && apt install -y build-essential libssl-dev libffi-dev python3-dev
RUN pip install poetry==1.1.11
# Copy in app files
COPY . .
# Create download directories
RUN mkdir -p /app/out
RUN mkdir -p /app/dl
# Create poetry venv
RUN poetry install
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]