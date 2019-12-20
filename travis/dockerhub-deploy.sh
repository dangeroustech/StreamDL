#!/bin/bash
set -ev
export DOCKER_CLI_EXPERIMENTAL=enabled
if [ "${TRAVIS_BRANCH}" = "master" ]; then
    DOCKER_TAG="stable"
else
    DOCKER_TAG="staging"
fi

if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
    docker login -u $DOCKER_USER -p $DOCKER_PASSWORD
    # Push stable manifest
    docker manifest create dangerous-tech/streamdl:${DOCKER_TAG} \
            dangerous-tech/streamdl:${DOCKER_TAG}-amd64 \
            dangerous-tech/streamdl:${DOCKER_TAG}-arm \
            dangerous-tech/streamdl:${DOCKER_TAG}-arm64

    docker manifest annotate dangerous-tech/streamdl:${DOCKER_TAG} dangerous-tech/streamdl:${DOCKER_TAG}-amd64 --arch amd64
    docker manifest annotate dangerous-tech/streamdl:${DOCKER_TAG} dangerous-tech/streamdl:${DOCKER_TAG}-arm --arch arm
    docker manifest annotate dangerous-tech/streamdl:${DOCKER_TAG} dangerous-tech/streamdl:${DOCKER_TAG}-arm64 --arch arm64

    docker manifest push dangerous-tech/streamdl:${DOCKER_TAG}
    # Push latest manifest
    docker manifest create dangerous-tech/streamdl:latest \
            dangerous-tech/streamdl:latest-amd64 \
            dangerous-tech/streamdl:latest-arm \
            dangerous-tech/streamdl:latest-arm64

    docker manifest annotate dangerous-tech/streamdl:latest dangerous-tech/streamdl:latest-amd64 --arch amd64
    docker manifest annotate dangerous-tech/streamdl:latest dangerous-tech/streamdl:latest-arm --arch arm
    docker manifest annotate dangerous-tech/streamdl:latest dangerous-tech/streamdl:latest-arm64 --arch arm64

    docker manifest push dangerous-tech/streamdl:latest
else
    docker images
fi