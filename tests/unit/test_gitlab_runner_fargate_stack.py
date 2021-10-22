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
import json
import pytest
import sys
import yaml
import os
from aws_cdk import core as cdk
from gitlab_ci_fargate_runner.gitlab_ci_fargate_runner_stack import (
    GitlabCiFargateRunnerStack,
)


env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"]
)
try:
    with open("./config/app.yml", "r") as stream:
        props = yaml.safe_load(stream)
except IOError:
    print("Error: Stack config file not found.")
except:
    print("Unexpected error:", sys.exc_info()[0])
    raise


def get_template():
    app = cdk.App()
    GitlabCiFargateRunnerStack(
        app, "GitlabrunnerBastionStack", env=env, props=props.get("bastion")
    )
    return json.dumps(app.synth().get_stack("GitlabrunnerBastionStack").template)


def test_iam_role_created():
    assert "AWS::IAM::Role" in get_template()


def test_s3_cache_bucket_created():
    assert "AWS::S3::Bucket" in get_template()


def test_bucket_policy_created():
    assert "AWS::S3::BucketPolicy" in get_template()


def test_SecurityGroup_created():
    assert "AWS::EC2::SecurityGroup" in get_template()


def test_LaunchConfiguration_created():
    assert "AWS::AutoScaling::LaunchConfiguration" in get_template()


def test_ecs_cluster_created():
    assert "AWS::ECS::Cluster" in get_template()


def test_ecs_cluster_created():
    assert "AWS::ECS::TaskDefinition" in get_template()
