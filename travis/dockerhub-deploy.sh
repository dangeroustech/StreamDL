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
    docker manifest create dangeroustech/streamdl:${DOCKER_TAG} \
            dangeroustech/streamdl:${DOCKER_TAG}-amd64 \
            dangeroustech/streamdl:${DOCKER_TAG}-arm \
            dangeroustech/streamdl:${DOCKER_TAG}-arm64

    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-amd64 --arch amd64
    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-arm --arch arm
    docker manifest annotate dangeroustech/streamdl:${DOCKER_TAG} dangeroustech/streamdl:${DOCKER_TAG}-arm64 --arch arm64

    docker manifest push dangeroustech/streamdl:${DOCKER_TAG}
    # Push latest manifest
    docker manifest create dangeroustech/streamdl:latest \
            dangeroustech/streamdl:latest-amd64 \
            dangeroustech/streamdl:latest-arm \
            dangeroustech/streamdl:latest-arm64

    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-amd64 --arch amd64
    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-arm --arch arm
    docker manifest annotate dangeroustech/streamdl:latest dangeroustech/streamdl:latest-arm64 --arch arm64

    docker manifest push dangeroustech/streamdl:latest
else
    docker images
fi