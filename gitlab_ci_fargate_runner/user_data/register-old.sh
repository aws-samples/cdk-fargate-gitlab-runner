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
ACCOUNT_ID="${__ACCOUNT_ID__}"
REGION="${__REGION__}"
GitLabServer="${__GITLAB_SERVER__}"
RunnerName="${__RUNNER_NAME__}"
GitLabRunnerToken="${__GITLAB_RUNNER_TOKEN__}"
LogOutputlimit="${__GITLAB_LOG_OUTPUT_LIMIT__}"
GitLabRunnerTags="${__GITLAB_RUNNER_TAGS__}"
AgentConfigSSMParam="${__SSM_CLOUDWATCH_AGENT_CONFIG__}"
CacheBucketName="${__CACHE_BUCKET__}"
# Install CloudWatch Agent
rpm -Uvh https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c ssm:${!AgentConfigSSMParam} -s
# Create gitlab runner directories
mkdir -p /opt/gitlab-runner/{metadata,builds,cache}
if [[ $? -ne 0 ]]
then
    echo "error creating gitlab runner directories" 
    exit 1
fi

curl -s "https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.rpm.sh" |  bash
yum install -y  install gitlab-runner

if [[ $? -ne 0 ]]
then
    echo "error installing fargate plugin" 
    exit 1
fi
curl -o /opt/gitlab-runner/fargate https://gitlab-runner-custom-fargate-downloads.s3.amazonaws.com/latest/fargate-linux-amd64

chmod 755 /opt/gitlab-runner/fargate
if [[ $? -ne 0 ]]
then
    echo "error installing fargate plugin " 
    exit 1
fi
gitlab-runner register --non-interactive --url \
    https://${!GitLabServer}  --registration-token \
    ${!GitLabRunnerToken} --description ${!RunnerName} \
    --builds-dir "/opt/gitlab-runner/builds" \
    --cache-dir "/opt/gitlab-runner/cache" \
    --output-limit ${!LogOutputlimit} \
    --tag-list ${!GitLabRunnerTags} \
    --cache-type "s3" \
    --cache-s3-bucket-name ${!CacheBucketName} \
    --cache-s3-bucket-location "${!REGION}" \
    --cache-shared --locked=true \
    --executor custom \
    --custom-config-exec /opt/gitlab-runner/fargate \
    --custom-config-args --config --custom-config-args  /etc/gitlab-runner/fargate.toml --custom-config-args  custom --custom-config-args config \
    --custom-prepare-exec /opt/gitlab-runner/fargate \
    --custom-prepare-args --config --custom-prepare-args  /etc/gitlab-runner/fargate.toml --custom-prepare-args custom --custom-prepare-args prepare \
    --custom-run-exec /opt/gitlab-runner/fargate \
    --custom-run-args  --config --custom-run-args  /etc/gitlab-runner/fargate.toml --custom-run-args  custom --custom-run-args  run \
    --custom-cleanup-exec /opt/gitlab-runner/fargate \
    --custom-cleanup-args --config --custom-cleanup-args  /etc/gitlab-runner/fargate.toml  --custom-cleanup-args custom --custom-cleanup-args  cleanup 
echo "Gitlab runner installed successfully"