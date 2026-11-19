# Contributing to IB Gateway Docker

First off, thank you for considering contributing to this project!
Your help is appreciated.

This document provides guidelines for contributing to the project. Please feel
free to propose changes to this document in a pull request.

## How to Contribute

We encourage you to contribute to this project! Please follow these steps:

1. **Create an Issue:** Before starting any work, please open an issue to
   discuss the bug or feature request. This allows us to give you feedback
   and prevent duplicated work. You can use the templates for [Bug Reports]
   (.github/ISSUE_TEMPLATE/bug_report.md) or [Feature Requests]
   (.github/ISSUE_TEMPLATE/feature_request.md).

2. **Fork the Repository:** Fork the project to your own GitHub account.

3. **Create a Branch:** Create a new branch for your changes. Use a descriptive
   name, like `fix/my-bug` or `feature/new-feature`.

## Development Setup

The project is structured to automatically build and release Docker images for
Interactive Brokers Gateway (IB Gateway) and Trader Workstation (TWS).

- **`image-files/`**: This is the main development directory. **All code
  changes must be made here.** This includes shell scripts, Dockerfile
  templates, and configuration templates.
- **`latest/` and `stable/`**: These directories contain the generated
  Dockerfiles and scripts for the latest and stable releases. **Do not edit
  files in these directories directly.** They are automatically generated from
  the files in `image-files/` and represent the built distribution.

To get started with development, you'll need to set up `pre-commit` to ensure your
changes adhere to the project's coding standards.

```bash
# Install pre-commit (if you don't have it)
# or pipx, brew, uv tool, etc.
pip install pre-commit

# Set up the git hook scripts
pre-commit install
```

## Making Changes

1. **Edit files in `image-files/`:** Make your desired code changes to the
   scripts, configurations, or templates within the `image-files/` directory.

2. **Update Release Files:** After making your changes, run the `update.sh`
   script. This script propagates your changes from `image-files/` to the
   `latest/` and `stable/` directories.

    ```bash
    # channel "stable/latest" and version 10.43.1c/10.37.1o for example
    ./update.sh <channel> <version>
    ```

3. **Build and Test Locally:** To test your changes, build the Docker image
   locally. First, create your `.env` file from the provided sample, then use
   `docker-compose` to build and run the container.

    ```bash
    # Create your environment file (only needs to be done once)
    cp .env-dist .env

    # Edit the .env file with your test configuration
    nano .env

    # Build and run the image (e.g., for the 'stable' release)
    docker-compose -f docker-compose.yml build --pull
    ```

    Ensure the container starts and functions as expected with your changes.

4. **Commit Your Changes:** **Crucially, all commits must be made to files
   within the `image-files/` directory.** Do NOT commit changes directly to
   `stable/` or `latest/` as these directories are managed automatically and
   direct commits will be rejected. Before committing, run the pre-commit hooks
   to format and lint your code.

    ```bash
    pre-commit run --all-files
    ```

    Once the hooks pass, you can commit your changes.

## Releasing

Releases are published by pushing a tag named `v<version>-<channel>`, for
example `v10.50.1h-stable`. The tag must point at a commit where
`<channel>/Dockerfile` already holds that version; the workflow fails
otherwise. The maintainer pushes the tag by hand.

`publish.yml` fails before building when the `ibgateway-<channel>@<version>`
release is missing. It then builds both images with SBOM and provenance, pushes
them to GHCR and Docker Hub, and signs them with keyless cosign. Finally it
creates the GitHub release of the tag with build info, the `cosign verify`
command, pinned compose files and `SHA256SUMS`.

The workflow supports two channel layouts. A channel directory with a
`Dockerfile.tws` (IBC layout) builds the two files and does not pin base
images. Without it, the workflow builds `target: gateway` and `target: tws` of
the channel `Dockerfile`, with base images pinned by digest. The tag decides the
layout, so rebuilds of older tags keep working.

### Weekly stable rebuild

`publish.yml` also runs every Monday at 04:00 UTC to rebuild `stable` with the
same Gateway version. A release tag is not moved or created: the rebuild exists
to pick up Ubuntu security updates that landed since the Gateway release.

- The image is built from the existing `v<version>-stable` tag, with the build
  cache disabled so apt packages and the moving `ubuntu` base are fetched fresh.
- The `stable`, minor (`10.50`) and version (`10.50.1h`) tags all move to the
  new image.
- Each rebuild signs the new images with identity
  `publish.yml@refs/heads/master` and appends an entry (UTC timestamp, run, digests,
  `cosign verify` command with the workflow SHA) to the GitHub release of the
  tag, creating that release if the tag has none.
- If the tag does not exist yet (release PR merged, tag not pushed), the run
  skips instead of failing.

Run it on demand with `workflow_dispatch` and `channel=stable`, optionally with
a `version`. Pushing rebuilds run only from `master`. Set `dry_run` to build
without pushing, signing or touching the release; on the two-file layout its TWS
build uses the previously published gateway image. Trigger it after a CVE when
waiting for Monday is not acceptable.

## Submitting a Pull Request

When you are ready to submit your contribution:

1. Push your branch to your forked repository.
2. Create a Pull Request against the `master` branch of the main repository.
3. In your Pull Request description, provide a clear summary of the changes and
   link to the issue you created.
4. We will review your PR, provide feedback, and merge it once it's ready.

Thank you for your contribution!
