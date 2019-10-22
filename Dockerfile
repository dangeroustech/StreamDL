FROM python:3.7-alpine
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# Install necessary software
RUN apk update && apk upgrade
RUN apk add --no-cache git ffmpeg
RUN pip3 install pipenv
# Copy in app files
RUN git clone https://github.com/biodrone/StreamDL /app
RUN git checkout dockerise
# Create out directory
RUN mkdir /app/out
# Create pipenv
RUN pipenv install -e .
ENTRYPOINT [ "/bin/ash", "/app/entrypoint.sh" ]
