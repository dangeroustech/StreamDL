FROM ubuntu:latest
WORKDIR /app
# Create in and out Directories
RUN mkdir /app/in
RUN mkdir /app/out
RUN apt-get update && apt-get upgrade -y
RUN apt-get install python3 git python3-pip -y
RUN pip3 install youtube-dl ffmpeg-python bs4 requests pyyaml
# Make ssh dir
RUN mkdir /root/.ssh/
# Copy over private key, and set permissions
ADD id_rsa /root/.ssh/id_rsa
# Create known_hosts
RUN touch /root/.ssh/known_hosts
# Add bitbuckets key
RUN ssh-keyscan bitbucket.org >> /root/.ssh/known_hosts
RUN git clone git@bitbucket.org:biodrone/cbdl.git
RUN rm /root/.ssh/id_rsa
WORKDIR /app/cbdl
RUN pwd
RUN ls -lah
RUN python3 cbdl.py -h

