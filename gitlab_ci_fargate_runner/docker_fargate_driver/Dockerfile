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

ARG GITLAB_RUNNER_VERSION

FROM gitlab/gitlab-runner:ubuntu-v$GITLAB_RUNNER_VERSION

RUN apt-get update \
    && apt-get install -y jq curl unzip gettext-base \
    && apt-get clean autoclean

# ---------------------------------------------------------------------------
# Install https://gitlab.com/gitlab-org/ci-cd/custom-executor-drivers/fargate 
#  Custom Driver for Fargate
# ---------------------------------------------------------------------------

ADD https://gitlab-runner-custom-fargate-downloads.s3.amazonaws.com/master/fargate-linux-amd64 /usr/local/bin/fargate-linux-amd64
RUN chmod +x /usr/local/bin/fargate-linux-amd64

# -------------------------------------------------------------------------------------
# Install https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
# Install AWS cli to retreive Secret
# -------------------------------------------------------------------------------------

ADD https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip /tmp/awscliv2.zip
RUN cd /tmp/ \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -f awscliv2.zip

# Copy the config template files to be used for generating our runner and driver config
COPY config_runner_template.toml /tmp/
COPY config_driver_template.toml /tmp/

# -------------------------------------------------------------------------------------
# Execute a startup script.
# https://success.docker.com/article/use-a-script-to-initialize-stateful-container-data
# for reference.
# -------------------------------------------------------------------------------------
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && ln -s /usr/local/bin/docker-entrypoint.sh / # backwards compat

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh", "gitlab-runner", "run"]