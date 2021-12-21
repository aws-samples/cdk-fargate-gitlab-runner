#!/bin/bash
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

# -----------------------------------------------------------------------------
# Important: this scripts depends on some predefined environment variables:
# - GITLAB_REGISTRATION_TOKEN (required): registration token for your project
# - GITLAB_URL (optional): the URL to the GitLab instance (defaults to https://gitlab.com)
# - RUNNER_TAG_LIST (optional): comma separated list of tags for the runner
# - FARGATE_CLUSTER (required): the AWS Fargate cluster name
# - FARGATE_REGION (required): the AWS region where the task should be started
# - FARGATE_SECURITY_GROUP (required): the AWS security group where the task
#   should be started
# - FARGATE_TASK_DEFINITION (required): the task definition used for the task
# -----------------------------------------------------------------------------

get_from_metadata() {
    # Query the unique security credentials generated for the task.
    # https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
    AWS_CREDENTIALS=$(curl -s 169.254.170.2${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI})

    # Read the `AccessKeyId`, `SecretAccessKey`, and `Token` values.
    export AWS_ACCESS_KEY_ID=$(echo $AWS_CREDENTIALS | jq '.AccessKeyId' --raw-output)
    export AWS_SECRET_ACCESS_KEY=$(echo $AWS_CREDENTIALS | jq '.SecretAccessKey' --raw-output)
    export AWS_SESSION_TOKEN=$(echo $AWS_CREDENTIALS | jq '.Token' --raw-output)

    # Default to https://gitlab.com if the GitLab URL was not specified
    export GITLAB_URL=${GITLAB_URL:=https://gitlab.com}

    AWS_METADATA=$(curl -s ${ECS_CONTAINER_METADATA_URI_V4}/task)
    # Find useful informations through metadata endpoint
    export CONTAINER_AZ=$(echo ${AWS_METADATA} | jq -r .AvailabilityZone)
    export CLUSTER_ARN=$(echo ${AWS_METADATA}  | jq -r  .Cluster)
    export TASK_ARN=$(echo ${AWS_METADATA} | jq -r .TaskARN)
    export FARGATE_SUBNET=$(aws ecs describe-tasks --cluster $CLUSTER_ARN --tasks $TASK_ARN | jq  -r '.tasks[].attachments[].details[] | select(.name=="subnetId").value')

}
###############################################################################
# Remove the Runner from the list of runners of the project identified by the
# authentication token.
#
# Arguments:
#   $1 - Authorization token obtained after registering the runner in the
#        project
###############################################################################
unregister_runner() {
    curl --request DELETE "${GITLAB_URL}/api/v4/runners" --form "token=$1"
}

###############################################################################
# Register the Runner in the desired project, identified by the registration
# token of that project.
#
# The function populates the "auth_token" variable with the authentication
# token for the registered Runner.
#
# Arguments:
#   $1 - Registration token
#   $2 - List of tags for the Runner, separated by comma
###############################################################################
register_runner() {

    runner_identification="RUNNER_${CONTAINER_AZ}"

    # Uses the environment variable "GITLAB_REGISTRATION_TOKEN" to register the runner

    result_json=$(
        curl --request POST "${GITLAB_URL}/api/v4/runners" \
            --form "token=$1" \
            --form "description=${runner_identification}" \
            --form "tag_list=$2"
    )

    # Read the authentication token

    export auth_token=$(echo $result_json | jq -r '.token')

    # Recreate the runner config.toml based on our template

    export RUNNER_NAME=$runner_identification
    export RUNNER_AUTH_TOKEN=$auth_token
    envsubst < /tmp/config_runner_template.toml > /etc/gitlab-runner/config.toml
}

###############################################################################
# Create the Fargate driver TOML configuration file based on a template
# that is persisted in the repository. It uses the environment variables
# passed to the container to set the correct values in that file.
#
# Globals:
#   - FARGATE_CLUSTER
#   - FARGATE_REGION
#   - FARGATE_SUBNET
#   - FARGATE_SECURITY_GROUP
#   - FARGATE_TASK_DEFINITION
###############################################################################
create_driver_config() {
    envsubst < /tmp/config_driver_template.toml > /etc/gitlab-runner/config_driver.toml
}

mkdir -p /log/
touch stderr.log stdout.log

## Redirecting Filehanders
ln -sf /proc/$$/fd/1 /log/stdout.log
ln -sf /proc/$$/fd/2 /log/stderr.log

## Pre execution handler
pre_execution_handler() {
    ## Pre Execution

    get_from_metadata

    create_driver_config

    # GITLAB_REGISTRATION_TOKEN Retreive from ECS Secret

    register_runner ${GITLAB_REGISTRATION_TOKEN} ${RUNNER_TAG_LIST}

}

## Post execution handler
post_execution_handler() {
  ## Post Execution
  unregister_runner ${auth_token}
}

## Sigterm Handler
sigterm_handler() { 
  if [ $pid -ne 0 ]; then
    # the above if statement is important because it ensures 
    # that the application has already started. without it you
    # could attempt cleanup steps if the application failed to
    # start, causing errors.
    kill -15 "$pid"
    wait "$pid"
    post_execution_handler
  fi
  exit 143; # 128 + 15 -- SIGTERM
}

## Setup signal trap
# on callback execute the specified handler
trap 'sigterm_handler' SIGTERM

## Initialization
pre_execution_handler

## Start Process

# run process in background and record PID
>/log/stdout.log 2>/log/stderr.log "$@" &
pid="$!"
# Application can log to stdout/stderr, /log/stdout.log or /log/stderr.log

## Wait forever until app dies
wait "$pid"
return_code="$?"

## Cleanup
post_execution_handler
# echo the return code of the application
exit $return_code