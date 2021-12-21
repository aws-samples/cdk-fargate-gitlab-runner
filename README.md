# CDK construct to deploy Fargate Gitlab runner

Many customers rely on GitLab and Gitlab CI/CD to automate their build, test, and deployment processes.  Gitlab CI/CD uses a Gitlab Runner to run jobs in a pipeline. In this project , we use [CDK](https://aws.amazon.com/cdk/)  to deploy a Gitlab/CI  runner  using  [AWS Fargate](https://aws.amazon.com/fargate/)  a serverless compute engine for containers that works with both [Amazon Elastic Container Service (ECS)](https://aws.amazon.com/ecs/) and [Amazon Elastic Kubernetes Service](https://aws.amazon.com/eks/).

# Solution Architecture 
![Architecture](/docs/img/GitlabCiRunnerServerless.png)
- [CDK construct to deploy Fargate Gitlab runner](#cdk-construct-to-deploy-fargate-gitlab-runner)
- [Solution Architecture](#solution-architecture)
  - [Limitations](#limitations)
- [Deployment Guide](#deployment-guide)
  - [Requirement](#requirement)
  - [Deployment](#deployment)
- [Configuration options](#configuration-options)
  - [Examples of advanced usage](#examples-of-advanced-usage)
    - [Building Docker image](#building-docker-image)
      - [Deploying](#deploying)
    - [Deploy an other task definition](#deploy-an-other-task-definition)
    - [Use a managed iam policy for your task_definiton execution role](#use-a-managed-iam-policy-for-your-task_definiton-execution-role)
    - [Use a custom inline iam policy for your task_definiton execution role](#use-a-custom-inline-iam-policy-for-your-task_definiton-execution-role)
    - [Specify stacks name](#specify-stacks-name)
- [CHANGELOG](#changelog)
- [LICENSE](#license)

## Limitations
- This solution doesn't support Windows workloads
  
# Deployment Guide 

## Requirement

- In order to deploy the CDK construct  you need to have an environment provisioned with **Python3.9**, [**Pipenv**](https://pipenv.pypa.io/en/latest/) and  **Pip3**. 
Check your Python version:  
    ```bash
    python --version 
    # Python 3.9.6
    pipenv --version
    # pipenv, version 2021.5.29
    pip3 --version
    # pip 21.1.3
    ``` 
- [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html)
- [Install the AWS CDK](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html) version >= 2.0.0
- [Install Docker](https://docs.docker.com/get-docker/) In order to build to Docker images, you need to have Docker engine installed on your machine.
- [AWS Account](https://aws.amazon.com/resources/create-account/)
- An AWS VPC, configure with a least a private subnet with a NAT Gateway attached. (see [here](https://github.com/awslabs/aws-cloudformation-templates/blob/master/aws/services/VPC/VPC_With_Managed_NAT_And_Private_Subnet.yaml) to have a exemple Cloudformation stack)

## Deployment

- Clone this repository 
- Validate prerequisites for CDK [here](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html#getting_started_prerequisites)
- Bootstrap your AWS account to use CDK following the AWS guide [here](https://docs.aws.amazon.com/cdk/latest/guide/bootstrapping.html)
```bash
cdk bootstrap aws://YOUR_ACCOUNT_ID/YOUR_REGION
``` 
- ### Export CDK environment variables
    - Linux or MacOS
    ```bash
    export CDK_DEFAULT_ACCOUNT=YOUR_ACCOUNT_ID
    export CDK_DEFAULT_REGION=YOUR_REGION
    ``` 
    - Windows
    ``` 
    setx CDK_DEFAULT_ACCOUNT YOUR_ACCOUNT_ID
    setx CDK_DEFAULT_REGION YOUR_REGION
    ``` 
- ### Enable service linked role for ECS 

    If it is your first time using ECS, you may need to manually enable the service linked role.

    ```bash 
    aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com
    ```
- ### Create Secret for Gitlab Token

    The Gitlab runner token should be stored in [AWS Secret manager](https://aws.amazon.com/secrets-manager/) as a key/velue, with key=token and value can be retrieved from Gitlab setting from settings/cicd/runners.

    ```bash 
    aws secretsmanager create-secret --name GitlabSecretToken \
    --description "Token used to register runner to Gitlab instance" \
    --secret-string '{ "token": "TOKEN_VALUE"}'
    ```

- ### Launch CDK stack
    
    The cdk application is composed on two stacks :
      - Main stack that deploys all the necessary resources for  gitlab runner , this includes S3 bucket, IAM roles, ECS Cluster, and an autoscaling group for bastion instance.
      - Task definition stack, this is used to deploy fargate task definitions with the corresponding Docker images that are used in the ci/cd jobs. The docker images are built  automticaly by  CDK from the directory `docker_images` and pushed to [ECR](https://aws.amazon.com/ecr/) registry
    <br />

    ```bash
    cd gitlab_ci_fargate_runner
    ```
    
    Copy `config/app.yml-example` to `config/app.yml` and replace values in the config file `config/app.yml` with your environment parameters

    ```yaml
    ---
    app_name: Gitlabrunner
    bastion:
        gitlab_runner_version: "14.5.1" 
        mng_min_size: 1 #Default 1
        mng_max_size: 2 #Default number of availibity zones of provided vpc 
        gitlab_server: gitlab.com # modify with gitlab server
        concurrent_jobs: 2 # put here the desired concurent jobs
        gitlab_runner_token_secret_name: my_secret # Put here the name of the gitlab tokensecret name stored in secret manager
        runner_tags: my_tag # put here liset of tags of gitlab runner
        VpcId: vpc-idxxxxxx # Your VpcID
    task_definition:
        gitlab_runner_version: "14.5.1"
        docker_image_name: amazonlinux # put here the defaul docker image to use
    tags: # Put tags as key: value pair
        ProjectName: Demo
        CostCenter: IT
    ```

    :warning: Mac M1 users :warning: you have to add `--platform=linux/amd64` after the `FROM` inside the Dockerfile to be able to build the images on your Mac ARM architecture. Fargate custom executor does currently support using Fargate on ARM. You can configure image in the [docker_images](docker_images) folder
    
    ```Dockerfile
    FROM --platform=linux/amd64 amazonlinux:2.0.20210813.1
    ...
    ```
  

    Install python dependencies:

    ```bash
    cd gitlab-ci-fargate-runner
    pipenv install
    # start docker service , it is used to build image
    ```

    Validate Cloudformation Template and deploy :

    ```bash
    pipenv run cdk synth  --all 
    pipenv run cdk deploy --all
    ```

    This will deploy two stacks, `GitlabrunnerBastionStack` and `{docker_image_name}TaskDefinitionStack`. Where **docker_image_name** is the value set config/app.yml

    You can [deploy an other task definition](#deploy-an-other-task-definition)

  - ### Testing

    Add  `.gitlab_ci.yml` to your project 

    Replace value of : 
    - **FARGATE_TASK_DEFINITION** with the value of the task definition id with the format : __{docker_image_name}:{version}.__ An increment of version occurs at each changes of the taskdefiniton. 
    - **CI_TAGSs** with the actual tags you specified in config/app : `bastion.runner_tags`
    
    ```yaml
    ---
    default:
    tags:
    # This tell Gitlab to use our newly created runners.
    # this sould correspond to runner_tags config/app.yml above
        - CI_TAGS

    variables:
    # Add variable FARGATE_TASK_DEFINITION to the task definition revision deployed in the stack above.
    # This variable can also be redefined per job.
        FARGATE_TASK_DEFINITION: "amazonlinux:1"
    stages:         
      - build
      - test
      - deploy

    build-job: # This job runs in the build stage, which runs first.
      stage: build
      script:
        - echo "Compiling the code..."
        - echo "Compile complete."

    unit-test-job:   # This job runs in the test stage.
      stage: test    # It only starts when the job in the build stage completes successfully.
      script:
        - echo "Running unit tests "
        - echo "Code coverage is XX%"

    deploy-job:      # This job runs in the deploy stage.
      stage: deploy  # It only runs when *both* jobs in the test stage complete successfully.
      script:
        - echo "Deploying application..."
        - echo "Application successfully deployed."

    ```

    After commiting and pushing the code update, the pipline starts  and uses the fargate runner to execute the jobs. The docker image used to execute the jobs is the one defined in Fargate task difinition. We can override the docker image, by creating a new task definition and set the variable **FARGATE_TASK_DEFINITION** in `.gitlab-ci.yml`.

    ![Results](/docs/img/gitlab-pipeline-screenshot.png)

  - ### Cleanup
    Run the command below to delete the resources that were created.

    - Delete the cdk stack
    ```bash
    pipenv run cdk destroy  --all  
    ```

    - Delete the secret created
    ```bash
    aws secretsmanager delete-secret --secret-id GitlabSecretToken \
        --recovery-window-in-days 7
    ```

# Configuration options

* __General__

| Configuration Key | CDK Context Key |                      Description                       | Required | Default value |
|:-----------------:|:-----------:|:------------------------------------------------------:|:--------:|:-------------:|
|     app_name      |      -      |                Name of your application                |   Yes    |       -       |
|       tags        |      -      | Key: value pair of Tags to apply to deployed resources |    No    |       -       |

* __Bastion__

|        Configuration Key        |   CDK Context Key    |                                                                          Description                                                                           | Required |      Default value       |
|:-------------------------------:|:----------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------:|:--------:|:------------------------:|
|      gitlab_runner_version      |        -         |                                                                Version of Gitlab Runner to use                                                                 |   Yes    |            -             |
|          desired_size           |        -         |                                                       Number of desired instance Task in Fargate Service                                                       |    No    |            1             |
|          gitlab_server          |        -         |                                                               Host of the Gitlab Server instance                                                               |    No    |        gitlab.com        |
|         concurrent_jobs         |        -         |                                                                    Number of concurent jobs                                                                    |    No    |            1             |
|               cpu               |        -         |    CPU Taskdefinition parameter see [documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size)     |    No    |           256            |
|             memory              |        -         | Memory Taskdefinition parameter see  [documentation](  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size ) |    No    |           512            |
| gitlab_runner_token_secret_name |        -         |                                                  Name of the gitlab tokensecret name stored in secret manager                                                  |   Yes    |            -             |
|         log_group_name          |        -         |                                                           Name of the LogGroup create in Cloudwatch                                                            |    No    |     /Gitlab/Runners/     |
|              VpcId              |        -         |                                                        VPC Id where the Gitlab Runner will be deployed                                                         |   Yes    |            -             |
|           stack_name            | BastionStackName |                                                           Name of the resulting Cloudformation Stack                                                           |    No    | `{app_name}BastionStack` |
|           runner_tags           |        -         |                                                                     Tags to add to runners                                                                     |    No    |            -             |


* __Task Definition__

|   Configuration Key   |       CDK Context Key       |                                                                          Description                                                                           | Required |                 Default value                  |
|:---------------------:|:-----------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------:|:--------:|:----------------------------------------------:|
| gitlab_runner_version |            -            |                                                                Version of Gitlab Runner to use                                                                 |   Yes    |                       -                        |
|          cpu          |           CPU           |    CPU Taskdefinition parameter see [documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size)     |    No    |                      256                       |
|   docker_image_name   |     DockerImageName     |                                          Name of the folder of the image (ex : amazonlinux) in `docker_images` folder                                          |   Yes    |                       -                        |
|   managed_policies    |   TaskManagedPolicies   |                                                                    Managed IAM policy Name                                                                     |    No    |                       -                        |
|        memory         |         Memory          | Memory Taskdefinition parameter see  [documentation](  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size ) |    No    |                      512                       |
|  iam_policy_template  |    TaskInlinePolicy     |                                                    Path to inline policy to add to ExecutionTaskRolePolicy                                                     |    No    |                       -                        |
|    log_group_name     |            -            |                                                           Name of the LogGroup create in Cloudwatch                                                            |    No    | "/Gitlab/TaskDefinitions/{docker_image_name}/" |
|      stack_name       | TaskDefinitionStackName |                                                               Resulting Cloudformation StackName                                                               |    No    |                      root                      |


## Examples of advanced usage

### Building Docker image 

You can use GitLab CI/CD with Docker to create Docker images. To be able to build Docker images inside a container, the traditionnal way uses DinD (Docker-in-Docker) which require to run the builder container as privileged.
This option is not available on AWS Fargate. 

An other option to build Docker image inside a Docker container is to use [Kaniko](https://github.com/GoogleContainerTools/kaniko). Kaniko can build Docker image inside a Docker container without the privileged mode. Also, it works out-of-the-box with ECR.

#### Deploying 

> The goal here is to build an image with Gitlab-CI and Kaniko and then push it to an ECR repository

Please follow the [Deployment Guide](#deployment-guide) before the instructions below. 

  - ##### Deploy the Kaniko task definition: 

  ```bash
  pipenv run cdk deploy -c DockerImageName=kaniko -c TaskManagedPolicies=AmazonEC2ContainerRegistryPowerUser kanikoTaskDefinitionStack
  ``` 

  - ##### Create an ECR repo

  ```bash 
  aws ecr create-repository \
    --repository-name kaniko-builder
  ```

  - ##### Configure your Git repository

    - In your Gitlab repository, create a directory named `build` and add your `Dockerfile` and `docker-entrypoint.sh` (you can use our example in `docker_images`.
  
    - Add this `.gitlab-ci.yml` at the root of your repo
    - Replace value of :
      - **<AWS_ACCOUNT_ID>** by the Account ID of your AWS account
      - **<AWS_REGION>**  and the region where you created your ECR repository.
      - **<CI_TAGS>** with the actual tags you specified in config/app : `bastion.runner_tags`
  
  ```yaml
  ---
  default:
    tags:
    # This tell Gitlab to use our newly created runners.
    # this sould correspond to runner_tags config/app.yml above
      - CI_TAGS

  variables:
    # Add variable FARGATE_TASK_DEFINITION to the task definition revision deployed in the stack above.
    # This variable can also be redefined per job.
    FARGATE_TASK_DEFINITION: "kaniko:1"

  stages:         
    - build

  docker_builder:
    stage: build
    variables:
      ENTRYPOINT: $CI_PROJECT_DIR/build
      IMAGE_TAG: myimage-$CI_COMMIT_SHORT_SHA
      REPO: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/kaniko-builder
    before_script:
      - echo creating docker config for ecr
      - mkdir -p /root/.docker
      - echo '{"credsStore":"ecr-login"}' > /root/.docker/config.json
      - export PATH=$PATH:/kaniko
      # Source the AWS env vars to retrieve credentials use to push image to ECR
      - source /etc/profile.d/set-aws-env-vars.sh
    script:
      - echo "build image and push"
      - /kaniko/executor --context $ENTRYPOINT --dockerfile $ENTRYPOINT/Dockerfile --destination $REPO:$IMAGE_TAG

  ```
  - ##### Cleanup 


    - Delete kaniko stack 

    ```bash 
    aws cloudformation delete-stack \
    --stack-name kanikoTaskDefinitionStack
    ```

    - Delete Kaniko ecr repo

    ```bash
    aws ecr delete-repository \
        --repository-name kaniko-builder \
        --force
    ```


### Deploy an other task definition

You can deploy more task definitions stacks by running:

```bash
pipenv run cdk deploy -c DockerImageName=docker_image_name -c Memory=1024 -c CPU=512  {docker_image_name}TaskDefinitionStack
``` 
Where **docker_image_name** to the name of the docker image found in the directory `docker_images`

### Use a managed iam policy for your task_definiton execution role 

You can use the context variable `TaskManagedPolicies` or as a parameter `task_definition.managed_policy` in your `app.config` file

```bash
pipenv run cdk deploy -c DockerImageName=kaniko -c Memory=1024 -c CPU=512 -c TaskManagedPolicies=AmazonEC2ContainerRegistryPowerUser
```
### Use a custom inline iam policy for your task_definiton execution role

```bash
pipenv run cdk deploy -c DockerImageName=python -c TaskInlinePolicy="./config/example_policy.json.j2"
```

### Specify stacks name

- Deploy both stack 

```bash
pipenv run cdk deploy -c BastionStackName="MY-CUSTOM-RUNNER" -c TaskDefinitionStackName="MyCustomImageTaskDefinition" --all
```

- Deploy only one stack 

```bash
export StackName="MY-CUSTOM-RUNNER" 
pipenv run cdk deploy -c BastionStackName=$StackName $StackName
```

# CHANGELOG
See the CHANGELOG file.
# LICENSE
This project is licensed under the MIT-0 License. See the LICENSE file.
