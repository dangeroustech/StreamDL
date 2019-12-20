#!/bin/bash
set -ev

PLATFORM=amd64
DOCKERFILE_LOCATION="./Dockerfile"
DOCKER_IMAGE="dangerous-tech"
if [ "${TRAVIS_BRANCH}" = "master" ]; then
    DOCKER_TAG="stable"
else
    DOCKER_TAG="staging"
fi

if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
    docker login -u $DOCKER_USER -p $DOCKER_PASSWORD

    buildctl build --frontend dockerfile.v0 \
        --progress=plain \
        --opt platform=linux/${PLATFORM} \
        --opt filename=${DOCKERFILE_LOCATION} \
        --opt build-arg:TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST} \
        --output type=image,name=docker.io/${DOCKER_USER}/${DOCKER_IMAGE}:${DOCKER_TAG}-${PLATFORM},push=true \
        --local dockerfile=. \
        --local context=.

    buildctl build --frontend dockerfile.v0 \
        --progress=plain \
        --opt platform=linux/${PLATFORM} \
        --opt filename=${DOCKERFILE_LOCATION} \
        --opt build-arg:TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST} \
        --output type=image,name=docker.io/${DOCKER_USER}/${DOCKER_IMAGE}:latest-${PLATFORM},push=true \
        --local dockerfile=. \
        --local context=.
else
    buildctl build --frontend dockerfile.v0 \
        --progress=plain \
        --opt platform=linux/${PLATFORM} \
        --opt filename=${DOCKERFILE_LOCATION} \
        --opt build-arg:TRAVIS_PULL_REQUEST=false \
        --output type=docker,name=${DOCKER_IMAGE}:${DOCKER_TAG}-${PLATFORM} \
        --local dockerfile=. \
        --local context=. \
        | docker load
fi 