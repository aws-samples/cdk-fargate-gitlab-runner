from typing import Protocol
from aws_cdk import core as cdk
from aws_cdk.aws_ec2 import InitCommand, SubnetType
import os
import sys
from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_ecs as ecs,
    aws_s3 as s3,
    aws_autoscaling as autoscaling,
    aws_secretsmanager as secretsmanager,
    core,
)
from aws_cdk.aws_ecr_assets import DockerImageAsset
from aws_cdk.aws_logs import LogGroup


class TaskDefinitionStack(cdk.Stack):
    def __init__(
        self, scope: cdk.Construct, construct_id: str, env, props, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)
        try:
            # fargate Execution role policies
            self.fargate_task_role_policies = {
                "AllowListOrgUnitParent": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:DescribeLogStreams",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                f"arn:aws:logs:{self.region}:{self.account}:log-group:/Gitlab/*"
                            ],
                        )
                    ]
                )
            }
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
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AmazonEC2ContainerRegistryReadOnly"
                    )
                ],
                inline_policies=self.fargate_task_role_policies,
            )
            # Add Fargate task definition
            default_docker_image = DockerImageAsset(
                self,
                props.get("docker_image_name"),
                directory=f'./docker_images/{props.get("docker_image_name")}',
            )

            awslogs_driver = ecs.CfnTaskDefinition.LogConfigurationProperty(
                log_driver="awslogs",
                options={
                    "awslogs-group": "/Gitlab/Runner/",
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
                cpu=props.get("task_definition_cpu"),
                memory=props.get("task_definition_memory"),
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
