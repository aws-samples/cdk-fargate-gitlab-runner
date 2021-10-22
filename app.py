#!/usr/bin/env python3
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
import os
import yaml
import sys
import random
from aws_cdk import core as cdk

# For consistency with TypeScript code, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core
from gitlab_ci_fargate_runner.gitlab_ci_fargate_runner_stack import (
    GitlabCiFargateRunnerStack,
)

from task_definitions.task_definition_stack import TaskDefinitionStack

try:
    with open("./config/app.yml", "r") as stream:
        props = yaml.safe_load(stream)
except IOError:
    print("Error: Stack config file not found.")
except:
    print("Unexpected error:", sys.exc_info()[0])
    raise
hex_random = hex(random.getrandbits(16))
app = core.App()
env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"]
)


if app.node.try_get_context("VpcId"):
    props["bastion"]["VpcId"] = app.node.try_get_context("VpcId")

if not props["bastion"]["VpcId"]:
    print("VPC_ID is mondatory cdk deploy -c vpcId=<YOUR_VPC_ID>")
    raise ValueError("VPC_ID is mondatory cdk deploy -c vpcId=<YOUR_VPC_ID>")

GitlabCiFargateRunnerStack(
    app, f"GitlabrunnerBastionStack", env=env, props=props.get("bastion")
)

if app.node.try_get_context("DockerImageName"):
    props["bastion"]["docker_image_name"] = app.node.try_get_context("DockerImageName")
if app.node.try_get_context("Memory"):
    props["bastion"]["task_definition_memory"] = app.node.try_get_context("Memory")
if app.node.try_get_context("CPU"):
    props["bastion"]["task_definition_cpu"] = app.node.try_get_context("CPU")

TaskDefinitionStack(
    app, f"{props['bastion']['docker_image_name']}TaskDefinitionStack", env=env, props=props.get("bastion")
)

app.synth()
