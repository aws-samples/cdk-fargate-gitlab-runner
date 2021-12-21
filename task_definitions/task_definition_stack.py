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
import aws_cdk as cdk
from constructs import Construct
import sys
from aws_cdk import (
    aws_iam as iam,
    aws_ecs as ecs,
    aws_logs as logs
)
from aws_cdk.aws_ecr_assets import DockerImageAsset
import json
from jinja2 import Template


class TaskDefinitionStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, env, props, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)
        try:

            self.fargate_execution_role = iam.Role(
                self,
                "GitlabExecutionRole",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "service-role/AmazonECSTaskExecutionRolePolicy"
                    )
                ],
            )
        
            self.fargate_task_role = iam.Role(
                self,
                "GitlabTaskRole",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(policy) for policy in props.get("managed_policies", [])
                ]
            )
    
            try:
                task_policies_template = props.get("iam_policy_template", "")
                with open(task_policies_template) as f:
                    j2_template = Template(f.read())
                rendered_template = j2_template.render(
                    region=self.region, account=self.account
                )
                task_policies = json.loads(rendered_template)
                self.fargate_task_role_policies = iam.Policy(
                    self,
                    "taskPolicy",
                    document=iam.PolicyDocument.from_json(task_policies),
                )
                self.fargate_task_role.attach_inline_policy(
                    self.fargate_task_role_policies
                )
            except IOError:
                print("No task policies template provided.")
            # Add Fargate task definition
            default_docker_image = DockerImageAsset(
                self,
                props.get("docker_image_name"),
                directory=f'./docker_images/{props.get("docker_image_name")}',
                build_args={
                    "GITLAB_RUNNER_VERSION": props.get("gitlab_runner_version") 
                }
            )

            # Create LogGroup
            self.log_group = logs.LogGroup(self,
                                           id="LogGroup",
                                           log_group_name=props.get(
                                               "log_group_name", f'/Gitlab/TaskDefinitions/{props.get("docker_image_name")}/'),
                                           removal_policy=cdk.RemovalPolicy.DESTROY,
                                           retention=logs.RetentionDays.ONE_DAY,
                                           )

            awslogs_driver = ecs.CfnTaskDefinition.LogConfigurationProperty(
                log_driver="awslogs",
                options={
                    "awslogs-group": self.log_group.log_group_name,
                    "awslogs-region": self.region,
                    "awslogs-stream-prefix": "fargate",
                },
            )
            port_mappings = [
                ecs.CfnTaskDefinition.PortMappingProperty(container_port=22)
            ]
            ci_coordinator = ecs.CfnTaskDefinition.ContainerDefinitionProperty(
                name="ci-coordinator",
                image=default_docker_image.image_uri,
                port_mappings=port_mappings,
                log_configuration=awslogs_driver,
            )
            self.fargate_task_definition = ecs.CfnTaskDefinition(
                self,
                f'{props.get("docker_image_name")}TaskDefinition',
                family=f'{props.get("docker_image_name")}',
                cpu=str(props.get("task_definition_cpu", 256)),
                memory=str(props.get("task_definition_memory", 512)),
                network_mode="awsvpc",
                task_role_arn=self.fargate_task_role.role_arn,
                execution_role_arn=self.fargate_execution_role.role_arn,
                container_definitions=[ci_coordinator],
            )

            self.output_props = props.copy()
            self.output_props["fargate_task_definition"] = self.fargate_task_definition

        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    @property
    def outputs(self):
        return self.output
