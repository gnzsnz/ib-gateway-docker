---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

## Describe the bug

A clear and concise description of what the bug is.

## To Reproduce

Steps to reproduce the behavior. Please include information related to docker,
ex docker run command, .env file, docker-compose.yml.

Please provide the output of `docker compose config`

## Expected

A clear and concise description of what you expected to happen.

## Container logs

If applicable, add the container logs `docker logs <CONTAINER>` or
`docker-compose logs` to help explain your problem.

## Versions

Please complete the following information:

- OS: [e.g. Windows]
- Docker version: [e.g. chrome, safari]
- Image Tag (`docker image inspect ghcr.io/gnzsnz/ib-gateway:tag`): [e.g.
  latest]
- Image Digest (`docker images --digests`): [e.g.
  sha256:60d9d54009b1b66908bbca1ebf5b8a03a39fe0cb35c2ab4023f6e41b55d17894]

## Additional context

Add any other context about the problem here.

What have you tried and failed.

My primary objective is to fix any bug on the container, ex Dockerfile, run.sh
script, docker-compose.yml. Please don't expect upstream issues to be solved
here (ex. IB gateway, IBC, etc)
