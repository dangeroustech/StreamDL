#!/bin/bash

set -ev
export DOCKER_CLI_EXPERIMENTAL=enabled

# Set Correct Branch
if [ "${TRAVIS_BRANCH}" = "master" ]; then
    DOCKER_TAG="stable"
else
    DOCKER_TAG="staging"
fi

# If This Isn't A PR, Push to Dockerhub
if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
    docker login -u $DOCKER_USER -p $DOCKER_PASSWORD

    docker manifest create dangeroustech/streamdl:${DOCKER_TAG} \
            dangeroustech/streamdl:${DOCKER_TAG}-amd64 \
            dangeroustech/streamdl:${DOCKER_TAG}-arm \
            dangeroustech/streamdl:${DOCKER_TAG}-arm64

    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-amd64 --arch amd64
    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-arm --arch arm
    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-arm64 --arch arm64

    docker manifest push dangeroustech/streamdl:${DOCKER_TAG}

    docker manifest create dangeroustech/streamdl:latest \
            dangeroustech/streamdl:latest-amd64 \
            dangeroustech/streamdl:latest-arm \
            dangeroustech/streamdl:latest-arm64

    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-amd64 --arch amd64
    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-arm --arch arm
    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-arm64 --arch arm64

    docker manifest push dangeroustech/streamdl:latest
else
    # If This is a PR, Check Images and Tags Are Correct
    docker images
fi