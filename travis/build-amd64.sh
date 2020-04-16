#!/bin/bash
set -ev

# Set Build Options
PLATFORM=amd64
DOCKERFILE_LOCATION="./Dockerfile"
DOCKER_IMAGE="streamdl"
DOCKER_ORG="dangeroustech"

# Set Correct Branch
if [ "${TRAVIS_BRANCH}" = "master" ]; then
    DOCKER_TAG="stable"
else
    DOCKER_TAG="staging"
fi

# If This Isn't A PR, Push to Dockerhub
if [ "${TRAVIS_PULL_REQUEST}" = "false" ]; then
    docker login -u $DOCKER_USER -p $DOCKER_PASSWORD

    buildctl build --frontend dockerfile.v0 \
        --progress=plain \
        --opt platform=linux/${PLATFORM} \
        --opt filename=${DOCKERFILE_LOCATION} \
        --opt build-arg:TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST} \
        --opt build-arg:TRAVIS_BRANCH=${TRAVIS_BRANCH} \
        --output type=image,name=docker.io/${DOCKER_ORG}/${DOCKER_IMAGE}:${DOCKER_TAG}-${PLATFORM},push=true \
        --local dockerfile=. \
        --local context=.

    buildctl build --frontend dockerfile.v0 \
        --progress=plain \
        --opt platform=linux/${PLATFORM} \
        --opt filename=${DOCKERFILE_LOCATION} \
        --opt build-arg:TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST} \
        --opt build-arg:TRAVIS_BRANCH=${TRAVIS_BRANCH} \
        --output type=image,name=docker.io/${DOCKER_ORG}/${DOCKER_IMAGE}:latest-${PLATFORM},push=true \
        --local dockerfile=. \
        --local context=.
else
    # If This is a PR, Build to Check for Errors
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