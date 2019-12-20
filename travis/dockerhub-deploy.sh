#!/bin/bash
set -ev
export DOCKER_CLI_EXPERIMENTAL=enabled
DOCKERHUB_ORG=dangerous-tech

if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
    docker login -u $DOCKER_USER -p $DOCKER_PASSWORD
    # Push stable manifest
    docker manifest create ${DOCKERHUB_ORG}/streamdl:stable \
            ${DOCKERHUB_ORG}/streamdl:stable-amd64 \
            ${DOCKERHUB_ORG}/streamdl:stable-arm \
            ${DOCKERHUB_ORG}/streamdl:stable-arm64

    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:stable ${DOCKERHUB_ORG}/streamdl:stable-amd64 --arch amd64
    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:stable ${DOCKERHUB_ORG}/streamdl:stable-arm --arch arm
    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:stable ${DOCKERHUB_ORG}/streamdl:stable-arm64 --arch arm64

    docker manifest push ${DOCKERHUB_ORG}/streamdl:stable
    # Push latest manifest
    docker manifest create ${DOCKERHUB_ORG}/streamdl:latest \
            ${DOCKERHUB_ORG}/streamdl:latest-amd64 \
            ${DOCKERHUB_ORG}/streamdl:latest-arm \
            ${DOCKERHUB_ORG}/streamdl:latest-arm64

    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:latest ${DOCKERHUB_ORG}/streamdl:latest-amd64 --arch amd64
    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:latest ${DOCKERHUB_ORG}/streamdl:latest-arm --arch arm
    docker manifest annotate ${DOCKERHUB_ORG}/streamdl:latest ${DOCKERHUB_ORG}/streamdl:latest-arm64 --arch arm64

    docker manifest push ${DOCKERHUB_ORG}/streamdl:latest
else
    docker images
fi