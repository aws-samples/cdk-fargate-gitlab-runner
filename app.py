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
from yaml import safe_load
import sys
import aws_cdk as cdk

from gitlab_ci_fargate_runner.gitlab_ci_fargate_runner_stack import (
    GitlabCiFargateRunnerStack,
)

from task_definitions.task_definition_stack import TaskDefinitionStack

# Check for required variable

if not os.getenv('CDK_DEFAULT_ACCOUNT'):
    raise ValueError("Missing requiered environment variables CDK_DEFAULT_ACCOUNT")
if not os.getenv('CDK_DEFAULT_REGION'):
    raise ValueError("Missing required environment variables CDK_DEFAULT_REGION")

# Load Config file
props = {}
try:
    with open("./config/app.yml", "r") as stream:
        props = safe_load(stream)
    stream.close()
except IOError:
    print("Error: Stack config file not found. Using defaults")
except:
    raise Exception(f'Unexpected error:{sys.exc_info()[0]}')

if not props["bastion"]["VpcId"]:
    print("VPC_ID is mondatory cdk deploy -c vpcId=<YOUR_VPC_ID>")
    raise ValueError("VPC_ID is mondatory cdk deploy -c vpcId=<YOUR_VPC_ID>")

app = cdk.App()
env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"]
)

# Add Tags for stack
for k,v in props.get("tags",{}).items():
    cdk.Tags.of(app).add(key=k,value=v)

if app.node.try_get_context("DockerImageName"):
    props["task_definition"]["docker_image_name"] = app.node.try_get_context("DockerImageName")
if app.node.try_get_context("Memory"):
    props["task_definition"]["task_definition_memory"] = app.node.try_get_context("Memory")
if app.node.try_get_context("CPU"):
    props["task_definition"]["task_definition_cpu"] = app.node.try_get_context("CPU")
if app.node.try_get_context("TaskManagedPolicies"):
    props["task_definition"]["managed_policies"] = app.node.try_get_context("TaskManagedPolicies").split(",")
if app.node.try_get_context("TaskInlinePolicy"):
    props["task_definition"]["iam_policy_template"] = app.node.try_get_context("TaskInlinePolicy")
if app.node.try_get_context("TaskDefinitionStackName"):
    props["task_definition"]["stack_name"] = app.node.try_get_context("TaskDefinitionStackName")
else:
    props["task_definition"]["stack_name"] = f"{props['task_definition']['docker_image_name']}TaskDefinitionStack"

TaskDefinitionStack(
    app, props["task_definition"]["stack_name"], env=env, props=props.get("task_definition")
)

if app.node.try_get_context("BastionStackName"):
    props["bastion"]["stack_name"] = app.node.try_get_context("BastionStackName")
else:
    props["bastion"]["stack_name"] = f'{props["app_name"]}BastionStack'

GitlabCiFargateRunnerStack(
    app, props["bastion"]["stack_name"], env=env, props=props.get("bastion")
)
app.synth()
