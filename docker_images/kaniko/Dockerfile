#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

FROM gcr.io/kaniko-project/executor:v1.7.0 AS kaniko
FROM amazonlinux:2.0.20210813.1

# ----------------------------------------------------------------
# Copy the kaniko executable and cloud container registry helpers.
# Then, set up the tool.
# ----------------------------------------------------------------
COPY --from=kaniko /kaniko/executor /kaniko/
COPY --from=kaniko /kaniko/docker-credential-gcr /kaniko/
COPY --from=kaniko /kaniko/docker-credential-ecr-login /kaniko/
COPY --from=kaniko /kaniko/docker-credential-acr /kaniko/

ENV DOCKER_CONFIG /kaniko/.docker/
ENV DOCKER_CREDENTIAL_GCR_CONFIG /kaniko/.config/gcloud/docker_credential_gcr_config.json
ENV PATH ${PATH}:/kaniko

RUN mkdir -p /kaniko/.docker \
    && mkdir -p /kaniko/ssl \
    && docker-credential-gcr config --token-source=env
    
# ---------------------------------------------------------------------
# Install https://github.com/krallin/tini - a very small 'init' process
# that helps processing signalls sent to the container properly.
# ---------------------------------------------------------------------
ARG TINI_VERSION=v0.19.0

RUN yum update -y && \
    yum install -y curl jq && \
    curl -Lo /usr/local/bin/tini https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-amd64 && \
    chmod +x /usr/local/bin/tini &&\
    yum -y clean all && \
    rm -rf /var/cache

# ----------------------------------------
# Install GitLab CI required dependencies.
# ----------------------------------------
ARG GITLAB_RUNNER_VERSION

RUN curl -Lo /usr/local/bin/gitlab-runner https://gitlab-runner-downloads.s3.amazonaws.com/v${GITLAB_RUNNER_VERSION}/binaries/gitlab-runner-linux-amd64 && \
    chmod +x /usr/local/bin/gitlab-runner && \
    gitlab-runner --version
# --------------------------------------------------------------------------
# Install and configure sshd.
# https://docs.docker.com/engine/examples/running_ssh_service for reference.
# --------------------------------------------------------------------------
RUN yum update  -y  && \
    yum install --skip-broken -y openssh-server && \
    mkdir -p /var/run/sshd &&\
    yum -y clean all && \
    rm -rf /var/cache

RUN yum install -y bash ca-certificates git &&\
    yum -y clean all && \
    rm -rf /var/cache

RUN useradd --shell /bin/bash -m --home-dir /home/ec2-user ec2-user
# -------------------------------------------------------------------------------------
# Execute a startup script.
# https://success.docker.com/article/use-a-script-to-initialize-stateful-container-data
# for reference.
# -------------------------------------------------------------------------------------
EXPOSE 22
CMD  ssh-keygen -A
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh
# USER ec2-user
ENTRYPOINT ["tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
