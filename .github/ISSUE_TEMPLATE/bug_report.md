---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

## Before you submit this issue

If this is not an issue but a request for help, please post it on the
[discussions](https://github.com/gnzsnz/ib-gateway-docker/discussions/categories/q-a)
section. There is a search function that will help you find solutions to common
problems.

Please make sure that you are running the latest version of `ib-gateway`:

```bash
docker pull ghcr.io/gnzsnz/ib-gateway:latest
```

Please make sure that you are using the [docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/docker-compose.yml) file provided as
an example - it is tested and you should be able to get things working by using it.

The example `.env` file on [README.md](https://github.com/gnzsnz/ib-gateway-docker/blob/master/README.md)
contains safe default values. Make sure you test the container using it as
starting point.

If after all this work you are still facing problems, please open an issue.

## Describe the bug

A clear and concise description of what the bug is.

## To Reproduce

Steps to reproduce the behavior. Please include information related to docker,
ex docker run command, .env file, docker-compose.yml.

Please provide the output of `docker compose config` **MANDATORY** ⚠️⚠️

## Expected

A clear and concise description of what you expected to happen.

## Container logs

If applicable, add the container logs `docker logs <CONTAINER>` or
`docker compose logs` to help explain your problem. **MANDATORY** ⚠️⚠️

## Versions

Please complete the following information:

- OS: [e.g. Windows]
- Docker version: [e.g. chrome, safari]
- Image Tag (`docker image inspect ghcr.io/gnzsnz/ib-gateway:tag`): [e.g.
  latest, stable] **MANDATORY** ⚠️⚠️
- Image Digest (`docker images --digests`): [e.g.
  sha256:60d9d54009b1b66908bbca1ebf5b8a03a39fe0cb35c2ab4023f6e41b55d17894]
  **MANDATORY** ⚠️⚠️

## Additional context

Add any other context about the problem here.

What have you tried and failed.

My primary objective is to fix any bug on the container, ex Dockerfile, run.sh
script, docker-compose.yml. Please don't expect upstream issues to be solved
here (ex. IB gateway, IBC, etc)
