#!/bin/sh
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
if [ -z "$SSH_PUBLIC_KEY" ]; then
  echo "Need your SSH public key as the SSH_PUBLIC_KEY env variable."
  exit 1
fi

# Create a folder to store user's SSH keys if it does not exist.
USER_SSH_KEYS_FOLDER=~/.ssh
[ ! -d "$USER_SSH_KEYS_FOLDER" ] && mkdir -p $USER_SSH_KEYS_FOLDER

# Copy contents from the `SSH_PUBLIC_KEY` environment variable
# to the `${USER_SSH_KEYS_FOLDER}/authorized_keys` file.
# The environment variable must be set when the container starts.
echo $SSH_PUBLIC_KEY > ${USER_SSH_KEYS_FOLDER}/authorized_keys

# Clear the `SSH_PUBLIC_KEY` environment variable.
unset SSH_PUBLIC_KEY

# Start the SSH daemon.
/usr/sbin/sshd -D
