#!/bin/sh
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

storeAWSTemporarySecurityCredentials() {

  # Skip AWS credentials processing if their relative URI is not present. 
  [ -z "$AWS_CONTAINER_CREDENTIALS_RELATIVE_URI" ] && return

  # Create a folder to store AWS settings if it does not exist.
  USER_AWS_SETTINGS_FOLDER=~/.aws
  [ ! -d "$USER_AWS_SETTINGS_FOLDER" ] && mkdir -p $USER_AWS_SETTINGS_FOLDER

  # Query the unique security credentials generated for the task.
  # https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
  AWS_CREDENTIALS=$(curl 169.254.170.2${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI})

  # Read the `AccessKeyId`, `SecretAccessKey`, and `Token` values.
  AWS_ACCESS_KEY_ID=$(echo $AWS_CREDENTIALS | jq '.AccessKeyId' --raw-output)
  AWS_SECRET_ACCESS_KEY=$(echo $AWS_CREDENTIALS | jq '.SecretAccessKey' --raw-output)
  AWS_SESSION_TOKEN=$(echo $AWS_CREDENTIALS | jq '.Token' --raw-output)

  # Create a file to store the temporary credentials on behalf of the user.
  USER_AWS_CREDENTIALS_FILE=${USER_AWS_SETTINGS_FOLDER}/credentials
  touch $USER_AWS_CREDENTIALS_FILE

  # Set the temporary credentials to the default AWS profile.
  #
  # S3 note: if you want to sign your requests using temporary security
  # credentials, the corresponding security token must be included.
  # https://docs.aws.amazon.com/AmazonS3/latest/dev/RESTAuthentication.html#UsingTemporarySecurityCredentials
  echo '[default]' > $USER_AWS_CREDENTIALS_FILE
  echo "aws_access_key_id=${AWS_ACCESS_KEY_ID}" >> $USER_AWS_CREDENTIALS_FILE
  echo "aws_secret_access_key=${AWS_SECRET_ACCESS_KEY}" >> $USER_AWS_CREDENTIALS_FILE
  echo "aws_session_token=${AWS_SESSION_TOKEN}" >> $USER_AWS_CREDENTIALS_FILE
}

propagateAWSEnvVarsAllLoginSessions() {

  # Store all AWS-related environment variables into a list.
  AWS_ENV_VARS=$(printenv | grep 'AWS_\|ECS_')

  # Create a script to export the AWS-related environment variables.
  SET_AWS_ENV_VARS_SCRIPT=/etc/profile.d/set-aws-env-vars.sh
  touch $SET_AWS_ENV_VARS_SCRIPT

  # Start the script from scratch.
  echo '' > $SET_AWS_ENV_VARS_SCRIPT

  # Write the `export environment variable` commands into the script.
  for VARIABLE in $AWS_ENV_VARS
  do
    echo "export $VARIABLE" >> $SET_AWS_ENV_VARS_SCRIPT
  done
}

storeAWSTemporarySecurityCredentials

propagateAWSEnvVarsAllLoginSessions

USER_SSH_KEYS_FOLDER=~/.ssh
[ ! -d ${USER_SSH_KEYS_FOLDER} ] && mkdir -p ${USER_SSH_KEYS_FOLDER}

# # Copy contents from the `SSH_PUBLIC_KEY` environment variable
# # to the `$USER_SSH_KEYS_FOLDER/authorized_keys` file.
# # The environment variable must be set when the container starts.
echo ${SSH_PUBLIC_KEY} > ${USER_SSH_KEYS_FOLDER}/authorized_keys

# # Clear the `SSH_PUBLIC_KEY` environment variable.
unset SSH_PUBLIC_KEY
ssh-keygen -A

# Start the SSH daemon
/usr/sbin/sshd -D
