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
FROM amazonlinux:2.0.20210813.1
# ---------------------------------------------------------------------
# Install https://github.com/krallin/tini - a very small 'init' process
# that helps processing signalls sent to the container properly.
# ---------------------------------------------------------------------
ARG TINI_VERSION=v0.19.0

RUN yum update -y && \
    yum install -y curl && \
    curl -Lo /usr/local/bin/tini https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-amd64 && \
    chmod +x /usr/local/bin/tini

# ----------------------------------------
# Install GitLab CI required dependencies.
# ----------------------------------------
ARG GITLAB_RUNNER_VERSION=v14.2.0

RUN curl -Lo /usr/local/bin/gitlab-runner https://gitlab-runner-downloads.s3.amazonaws.com/${GITLAB_RUNNER_VERSION}/binaries/gitlab-runner-linux-amd64 && \
    chmod +x /usr/local/bin/gitlab-runner && \
    gitlab-runner --version
# --------------------------------------------------------------------------
# Install and configure sshd.
# https://docs.docker.com/engine/examples/running_ssh_service for reference.
# --------------------------------------------------------------------------
# RUN useradd --uid 1000 --shell /bin/bash -m --home-dir /home/ec2-user ec2-user
#     # sed -i 's/%wheel\s.*/%wheel ALL=NOPASSWD:ALL/' /etc/sudoers && \
#     # usermod -a -G ec2-users ec2-user
RUN yum update  -y  && \
    yum install --skip-broken -y openssh-server && \
    mkdir -p /var/run/sshd 

# RUN curl -s "https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.rpm.sh" |  bash && \
#     yum install --skip-broken -y  install gitlab-runner && \
#     # Test if the downloaded file was indeed a binary and not, for example,
#     # an HTML page representing S3's internal server error message or something
#     # like that.
#     gitlab-runner --version

# # RUN yum install -y bash ca-certificates git git-lfs && \
# #     git-lfs install --skip-repo

RUN yum install --skip-broken -y bash ca-certificates git 
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
