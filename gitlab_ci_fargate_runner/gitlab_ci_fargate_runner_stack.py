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


class GitlabCiFargateRunnerStack(cdk.Stack):
    def __init__(
        self, scope: cdk.Construct, construct_id: str, env, props, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)
        # Lookup for VPC
        self.vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=props.get("VpcId"))

        try:
            cachebucket = s3.Bucket(
                self,
                "gitlabrunnercachebucket",
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.KMS_MANAGED,
                removal_policy=core.RemovalPolicy.DESTROY,
                enforce_ssl=True,
            )
            self.cache_bucket = cachebucket

            bastion_role_policies = {
                "AllowSSMRead": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["ssm:GetParameter"],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/Gitlab/*"
                            ],
                        )
                    ]
                ),
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
                ),
                "AllowSecreManagerRetrieve": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[
                                f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{props.get('gitlab_runner_token_secret_name')}*"
                            ],
                        )
                    ]
                ),
            }
            # Ceate IAM roles
            self.bastion_role = iam.Role(
                self,
                "GitlabBastionRole",
                assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "service-role/AmazonEC2RoleforSSM"
                    ),
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AmazonECS_FullAccess"
                    ),
                ],
                inline_policies=bastion_role_policies,
            )

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

            # userdata = ec2.UserData.for_linux(shebang="#!/bin/bash -xe")
            # userdata.add_commands()
            root_volume = autoscaling.BlockDevice(
                device_name="/dev/sda1",
                volume=autoscaling.BlockDeviceVolume.ebs(
                    volume_size=10, encrypted=True, delete_on_termination=True
                ),
            )



            self.sg_bastion = ec2.SecurityGroup(
                self, id="bastion_sg", vpc=self.vpc, allow_all_outbound=False
            )
            self.sg_bastion.add_ingress_rule(
                peer=self.sg_bastion, connection=ec2.Port.tcp(22)
            )
            self.sg_bastion.add_egress_rule(
                peer=self.sg_bastion, connection=ec2.Port.tcp(22)
            )
            self.sg_bastion.add_egress_rule(
                peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(443)
            )
                    
            # asg_1a.add_security_group(self.sg_bastion)

            asg_1a = autoscaling.AutoScalingGroup(
                self,
                "GitlabrunnerAsg1a",
                vpc=self.vpc,
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.NANO
                ),
                machine_image=ec2.AmazonLinuxImage(
                    generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                    storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE,
                ),
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=SubnetType.PRIVATE,
                    availability_zones=[f"{self.region}a"],
                ),
                signals=autoscaling.Signals.wait_for_all(),
                role=self.bastion_role,
                key_name=props.get("ssh_key_name") or None,
                block_devices=[root_volume],
                allow_all_outbound=False,
                security_group=self.sg_bastion 
            )
            asg_1b = autoscaling.AutoScalingGroup(
                self,
                "GitlabrunnerAsg1b",
                vpc=self.vpc,
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.NANO
                ),
                machine_image=ec2.AmazonLinuxImage(
                    generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                    storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE,
                ),
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=SubnetType.PRIVATE,
                    availability_zones=[f"{self.region}b"],
                ),
                signals=autoscaling.Signals.wait_for_all(),
                role=self.bastion_role,
                key_name=props.get("ssh_key_name") or None,
                block_devices=[root_volume],
                allow_all_outbound=False,
                security_group=self.sg_bastion 
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
                f"{self.stack_name}-cluser",
                cluster_name=f"{self.stack_name}-cluser",
                capacity_providers=["FARGATE", "FARGATE_SPOT"],
                default_capacity_provider_strategy=[
                    fargate_spot_strategy,
                    fargate_strategy,
                ],
                cluster_settings=[enbale_containerInsights],
            )
            # # Add Fargate task definition
            docker_image = DockerImageAsset(
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
                image=docker_image.image_uri,
                port_mappings=port_mappings,
                log_configuration=awslogs_driver,
            )
            self.fargate_task_definition = ecs.CfnTaskDefinition(
                self,
                f"{self.stack_name}{props.get('docker_image_name')}",
                family=f"{props.get('docker_image_name')}",
                cpu=props.get("task_definition_cpu"),
                memory=props.get("task_definition_memory"),
                network_mode="awsvpc",
                task_role_arn=self.fargate_task_role.role_arn,
                execution_role_arn=self.fargate_execution_role.role_arn,
                container_definitions=[ci_coordinator],
            )
            # SSM parameter to cloudwatch agent log
            with open("./config/cloudwatch_agent.json", "r") as cloudwatch_agent_config:
                cloud_watch_config_param = ssm.StringParameter(
                    self,
                    "CloudWatchAgentConfig",
                    string_value=cloudwatch_agent_config.read(),
                    description="CLoudwatch agent config",
                )
            cloudwatch_agent_config.close
            cloud_watch_config_param.grant_read(self.bastion_role)

            self.addLauncheConfiguration(asg_1a, props, "a", cloud_watch_config_param.parameter_name)
            self.addLauncheConfiguration(asg_1b, props, "b", cloud_watch_config_param.parameter_name)
            self.output_props = props.copy()
            self.output_props["vpc"] = self.vpc
            self.output_props["fargate_task_definition"] = self.fargate_task_definition

        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    # ----------------------------------------------------
    # Methode to add launch template to autoscaling group
    # ----------------------------------------------------
    def addLauncheConfiguration(self, asg: autoscaling, props, az, cloudwatch_agent_config_ssm_param_name):
        subnet_id = ""

        userdata_env_mappings = {
            "__ACCOUNT_ID__": self.account,
            "__REGION__": self.region,
            "__GITLAB_SERVER__": props.get("gitlab_server"),
            "__RUNNER_NAME__": f"{self.stack_name}-{az}-runner",
            "__GITLAB_RUNNER_TOKEN_SECRET_NAME__": props.get(
                "gitlab_runner_token_secret_name"
            ),
            "__GITLAB_RUNNER_TAGS__": props.get("runner_tags"),
            "__GITLAB_LOG_OUTPUT_LIMIT__": props.get("runner_log_output_limit"),
            "__SSM_CLOUDWATCH_AGENT_CONFIG__": cloudwatch_agent_config_ssm_param_name,
            "__CACHE_BUCKET__": self.cache_bucket.bucket_name,
            "__GITLAB_RUNNER_VERSION__": props.get("gitlab_runner_version"),
        }
        with open(
            "./gitlab_ci_fargate_runner/user_data/register.sh", "r"
        ) as user_data_h:
            # Use a substitution
            user_data_sub = core.Fn.sub(user_data_h.read(), userdata_env_mappings)
            app_user_data = ec2.UserData.custom(user_data_sub)
        user_data_h.close

        subnet_ids = self.vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE,
            availability_zones=[f"{self.region}{az}"],
        ).subnet_ids
        if subnet_ids:
            subnet_id = subnet_ids[0]
        try:
            gitlab_env_mappings = {
                "__ACCOUNT_ID__": self.account,
                "__REGION__": self.region,
                "__ECS_CLUSTER__": f"{self.stack_name}-cluser",
                "__SUBNET_ID__": subnet_id,
                "__CONCURRENT_JOBS__": props.get("concurrent_jobs"),
                "__SECURITY_GROUP_ID__": self.sg_bastion.security_group_id,
                "__TASK_DEFINITION__": self.fargate_task_definition.ref,
                "__SSH_USERNAME__": props.get("default_ssh_username"),
            }
            with open("./config/fargate.toml", "r") as gitlab_fargate_h:
                gitlab_fargate_sub = core.Fn.sub(
                    gitlab_fargate_h.read(), gitlab_env_mappings
                )
            gitlab_fargate_h.close

            with open("./config/config.toml", "r") as gitlab_config_h:
                gitlab_config_sub = core.Fn.sub(
                    gitlab_config_h.read(), gitlab_env_mappings
                )
            gitlab_config_h.close

            asg_cloudformation_init_configsets = ec2.CloudFormationInit.from_config_sets(
                config_sets={"default": ["setup", "packages", "config", "register"]},
                configs={
                    "setup": ec2.InitConfig(
                        [
                            # add gitlab runner repo
                            ec2.InitCommand.shell_command(
                                "curl -s https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.rpm.sh|  bash",
                                key="add_gitlab_runner_repo",
                            ),
                        ]
                    ),
                    "packages": ec2.InitConfig(
                        [
                            # Install an Amazon Linux package using yum
                            ec2.InitPackage.yum(
                                f"gitlab-runner-{props.get('gitlab_runner_version')}"
                            )
                        ]
                    ),
                    "config": ec2.InitConfig(
                        [
                            # ec2.InitGroup.from_name("gitlab-runner"),
                            # ec2.InitUser.from_name("gitlab-runner"),
                            ec2.InitFile.from_string(
                                "/etc/gitlab-runner/config.toml",
                                gitlab_config_sub,
                                group="root",
                                owner="root",
                                mode="0644",
                            ),
                            ec2.InitFile.from_string(
                                "/etc/gitlab-runner/fargate.toml",
                                gitlab_fargate_sub,
                                group="root",
                                owner="root",
                                mode="0644",
                            ),
                            ec2.InitFile.from_file_inline(
                                "/etc/systemd/system/gitlab-runner.service",
                                "./gitlab_ci_fargate_runner/services/gitlab-runner.service",
                                group="root",
                                owner="root",
                                mode="0644",
                            ),
                            ec2.InitFile.from_string(
                                "/etc/rsyslog.d/25-gitlab-runner.conf",
                                ':programname, isequal, "gitlab-runner" /var/log/gitlab-runner.log',
                                group="root",
                                owner="root",
                                mode="0644",
                            ),
                        ]
                    ),
                    "register": ec2.InitConfig(
                        [
                            ec2.InitCommand.shell_command(
                                user_data_sub, key="register-runner"
                            )
                        ]
                    ),
                },
            )
            asg.apply_cloud_formation_init(
                asg_cloudformation_init_configsets, print_log=True
            )
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    @property
    def outputs(self):
        return self.output_props
