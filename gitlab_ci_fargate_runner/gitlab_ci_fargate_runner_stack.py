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
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_s3 as s3,
    aws_autoscaling as autoscaling,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager

)
from aws_cdk.aws_ecr_assets import DockerImageAsset


class GitlabCiFargateRunnerStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, env, props, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)
        # Lookup for VPC
        self.vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=props.get("VpcId"))
        self.gitlab_token_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "gitlabRegistrationToken",
            props.get("gitlab_runner_token_secret_name"),
        )

        try:
            cachebucket = s3.Bucket(
                self,
                "gitlabrunnercachebucket",
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.KMS_MANAGED,
                removal_policy=cdk.RemovalPolicy.DESTROY,
                enforce_ssl=True,
            )
            self.cache_bucket = cachebucket

            # IAM Roles

            self.fargate_execution_role_policies = {
                "FargateExec": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssmmessages:CreateControlChannel",
                                "ssmmessages:CreateDataChannel",
                                "ssmmessages:OpenControlChannel",
                                "ssmmessages:OpenDataChannel"
                            ],
                             resources=["*"]
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
                inline_policies=self.fargate_execution_role_policies
            )

            self.fargate_task_role_policies = {
                "FargateTask": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:PutObject",
                                "s3:GetObjectVersion",
                                "s3:GetObject",
                                "s3:DeleteObject",
                            ],
                            resources=[f"{self.cache_bucket.bucket_arn}/*"],
                        )
                    ]
                )
            }

            self.gitlab_token_secret.grant_read(self.fargate_execution_role)

            # Create IAM roles

            self.fargate_task_role = iam.Role(
                self,
                "GitlabRunnerTaskRole",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AmazonECS_FullAccess"
                    )
                ],
                inline_policies=self.fargate_task_role_policies,
            )

            # Create LogGroup
            self.log_group = logs.LogGroup(self,
                                           id="LogGroup",
                                           log_group_name=props.get(
                                               "log_group_name", "/Gitlab/Runners/"),
                                           removal_policy=cdk.RemovalPolicy.DESTROY,
                                           retention=logs.RetentionDays.ONE_DAY,
                                           )
            # Create SG
            self.sg_runner = ec2.SecurityGroup(
                self, id="GitlabRunner", vpc=self.vpc, allow_all_outbound=False
            )
            self.sg_runner.add_ingress_rule(
                peer=self.sg_runner, connection=ec2.Port.tcp(22)
            )
            self.sg_runner.add_egress_rule(
                peer=self.sg_runner, connection=ec2.Port.tcp(22)
            )
            self.sg_runner.add_egress_rule(
                peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(443)
            )
            self.sg_runner.add_egress_rule(
                peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(80)
            )

            # # Add ECS Cluster
            fargate_spot_strategy = ecs.CfnCluster.CapacityProviderStrategyItemProperty(
                capacity_provider="FARGATE_SPOT", weight=100
            )
            fargate_strategy = ecs.CfnCluster.CapacityProviderStrategyItemProperty(
                capacity_provider="FARGATE", weight=10
            )
            enbale_containerInsights = ecs.CfnCluster.ClusterSettingsProperty(
                name="containerInsights", value="enabled"
            )
            self.fargate_cluster = ecs.CfnCluster(
                self,
                f"{self.stack_name}-cluster",
                cluster_name=f"{self.stack_name}-cluster",
                capacity_providers=["FARGATE", "FARGATE_SPOT"],
                default_capacity_provider_strategy=[
                    fargate_spot_strategy,
                    fargate_strategy,
                ],
                cluster_settings=[enbale_containerInsights],
            )

            # Add Fargate task definition
            gitlab_runner = DockerImageAsset(
                self,
                "GitlabRunnerImage",
                directory="./gitlab_ci_fargate_runner/docker_fargate_driver",
                build_args={
                    "GITLAB_RUNNER_VERSION": props.get("gitlab_runner_version")
                }
            )

            runner_environment = [
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="FARGATE_CLUSTER", value=f"{self.stack_name}-cluster"),
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="FARGATE_REGION", value=self.region),
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="FARGATE_SECURITY_GROUP", value=self.sg_runner.security_group_id),
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="RUNNER_TAG_LIST", value=props.get("runner_tags")),
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="CACHE_BUCKET", value=self.cache_bucket.bucket_name),
                ecs.CfnTaskDefinition.KeyValuePairProperty(
                    name="CACHE_BUCKET_REGION", value=self.region)
            ]

            runner_secrets = [ecs.CfnTaskDefinition.SecretProperty(
                name="GITLAB_REGISTRATION_TOKEN",
                value_from=ecs.Secret.from_secrets_manager(
                    self.gitlab_token_secret, "token"
                ).arn
            )]

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
            runner = ecs.CfnTaskDefinition.ContainerDefinitionProperty(
                name="gitlab-runner",
                image=gitlab_runner.image_uri,
                port_mappings=port_mappings,
                log_configuration=awslogs_driver,
                environment=runner_environment,
                secrets=runner_secrets,
                linux_parameters=ecs.CfnTaskDefinition.LinuxParametersProperty(
                    init_process_enabled=True,
                ),
                interactive=True
            )

            self.fargate_task_definition = ecs.CfnTaskDefinition(
                self,
                'GitlabRunnerTaskDefinition',
                family="gitlab-runner",
                cpu=str(props.get("task_definition_cpu", 256)),
                memory=str(props.get("task_definition_memory", 512)),
                network_mode="awsvpc",
                task_role_arn=self.fargate_task_role.role_arn,
                execution_role_arn=self.fargate_execution_role.role_arn,
                container_definitions=[runner]
            )

            self.gitlab_service = ecs.CfnService(
                self,
                "GitlabRunnerService",
                cluster=self.fargate_cluster.ref,
                task_definition=self.fargate_task_definition.ref,
                deployment_configuration=ecs.CfnService.DeploymentConfigurationProperty(
                    deployment_circuit_breaker=ecs.CfnService.DeploymentCircuitBreakerProperty(
                        enable=False,
                        rollback=False
                    ),
                    maximum_percent=100,
                    minimum_healthy_percent=0
                ),
                deployment_controller=ecs.CfnService.DeploymentControllerProperty(
                    type="ECS"
                ),
                desired_count=props.get("desired_count",1),
                enable_ecs_managed_tags=True,
                enable_execute_command=True,
                network_configuration=ecs.CfnService.NetworkConfigurationProperty(
                    awsvpc_configuration=ecs.CfnService.AwsVpcConfigurationProperty(
                        subnets=self.vpc.select_subnets(
                            subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT).subnet_ids,
                        security_groups=[self.sg_runner.security_group_id]
                    )
                ),

            )

            self.output_props = props.copy()
            self.output_props["vpc"] = self.vpc
            self.output_props["log_group_name"] = self.log_group.log_group_name

        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    @property
    def outputs(self):
        return self.output_props
