# CDK construct to deploy Fargate Gitlab runner

Many customers rely on GitLab and Gitlab CI/CD to automate their build, test, and deployment processes.  Gitlab CI/CD uses a Gitlab Runner to run jobs in a pipeline. In this project , we use [CDK](https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwjvqs2Z8I_zAhUPZMAKHUNHCsMQFnoECAQQAw&url=https%3A%2F%2Faws.amazon.com%2Fcdk%2F&usg=AOvVaw2tPZlF03QH3o_EKwTkN7cO)  to deploy a Gitlab/CI  runner  using  [AWS Fargate](https://aws.amazon.com/fargate/)  a serverless compute engine for containers that works with both [Amazon Elastic Container Service (ECS)](https://aws.amazon.com/ecs/) and [Amazon Elastic Kubernetes Service](https://aws.amazon.com/eks/).

## Solution Architecture 
![Architecture](/docs/img/GitlabCIRunnerFargate.png)

## Limitations
- This solution doesn't support  Docker in Docker (Dind) workloads 
- This solution doesn't support Windows workloads
## Installation Guide
### Requirmement

- In order to deploy the CDK construct  you need to have an environment provisioned with **Python3.9**, [**Pipenv**](https://pipenv.pypa.io/en/latest/) and  **Pip3**. 
Check your Python version:  
    ```
    # python --version 
    Python 3.9.6
    # pipenv --version
    pipenv, version 2021.5.29
    # pip3 --version
    pip 21.1.3
    ``` 
- [Install the AWS CDK](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html)
### Deployment
- Clone this repository 
- Bootstrap your AWS account to use CDK following the AWS guide [here](https://docs.aws.amazon.com/cdk/latest/guide/bootstrapping.html)
```
# cdk bootstrap aws://YOUR_ACCOUNT_ID/YOUR_REGION
``` 
- ##### Export CDK environment variables
    - Linux or MacOS
    ``` 
    # export CDK_DEFAULT_ACCOUNT=YOUR_ACCOUNT_ID`
    # export CDK_DEFAULT_REGION=YOUR_REGION`
    ``` 
    - Windows
    ``` 
    setx CDK_DEFAULT_ACCOUNT YOUR_ACCOUNT_ID
    setx CDK_DEFAULT_REGION YOUR_REGION
    ``` 

- ##### Launch CDK stack
    The cdk application is composed on two stacks :
    - Main stack that deploys all the necessary resources for  gitlab runner , this includes S3 bucket, IAM roles, ECS Cluster, and an autoscaling group for bastion instance.
    - Task definition stack, this is used to deploy fargate task definitions with the corresponding Docker images that are used in the ci/cd jobs. The docker images are built  automticaly by  CDK from the directory ` docker_images` and pushed to [ECR](https://aws.amazon.com/ecr/) registry
    ``` 
    # cd gitlab-ci-fargate-runner
    ```
    Copy `confg/app.yml-example` to `confg/app.yml` and replace values in the config file `confg/app.yml` with your environment parameters
    ```yaml
    ---
    # Gitlab fargate runner stack parameters
    app_name: gitlab-ci-fargate-runner
    bastion:
      gitlab_runner_version: Gitlab runner version (14.2.0-1)
      VpcId: VPC id on where to deploy the bastion runners, it can also be provided by cdk -c
      gitlab_server: Gitlab server name (ex, gitlab.com)
      gitlab_runner_token_secret_name: Secret Manager secret name for gitlab token
      runner_tags: Gitlab ci tags that are used in .gitlab-ci.yml
      runner_log_output_limit: Limit for console output log (4096)  see (https://docs.gitlab.com/runner/configuration/advanced-configuration.html)
      concurrent_jobs: Number of concurent jobs for this runner
      default_ssh_username: root
      docker_image_name: default docker image to be deployed with this stack, the images are in docker_images directory
      task_definition_cpu: "512" see (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html)
      task_definition_memory: "1024"  see (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html)
    ...
    ```
    ``` 
    # cd gitlab-ci-fargate-runner
    # pipenv install
    # start docker service , it is used to build image 
    # pipenv run cdk synth  --all \
    # pipenv run cdk deploy --all
    
    ``` 
    This will deploy two stacks, `GitlabrunnerBastionStack` and `amazonlinuxTaskDefinitionStack`. 

    You can deploy more task definitions stacks by running:
    ``` 
    # pipenv run cdk deploy -c DockerImageName=DOCKER_IMAGE_NAME -c Memory=1024 -c CPU=512  {DOCKER_IMAGE_NAME}TaskDefinitionStack
    ``` 
    Where DOCKER_IMAGE_NAME to the name of the docker image found in the directory `docker_images`
### Testing
Add  .gitlab_ci.yml to your project 
```yaml
---
    variables:
# Add variable FARGATE_TASK_DEFINITION to the task definition revision deployed in the stack above.
# This variable can also be redefined per job.
      FARGATE_TASK_DEFINITION: "amazonlinux:1"
    stages:         
      - build
      - test
      - deploy

    build-job:       # This job runs in the build stage, which runs first.
    stage: build
    script:
      - echo "Compiling the code..."
      - echo "Compile complete."
    tags:
      - ci-tag ( this sould correspond to GITLAB_TAGS confg/app.yml  above)

    unit-test-job:   # This job runs in the test stage.
    stage: test    # It only starts when the job in the build stage completes successfully.
    script:
      - echo "Running unit tests "
      - echo "Code coverage is XX%"
    tags:
      - ci-tag
    deploy-job:      # This job runs in the deploy stage.
    stage: deploy  # It only runs when *both* jobs in the test stage complete successfully.
    script:
      - echo "Deploying application..."
      - echo "Application successfully deployed."
    tags:
      - ci-tag ( this sould the same as  GITLAB_TAGS in confg/app.yml  above)
...
```
After commiting and pushing the code update, the pipline starts  and uses the fargate runner to execute the jobs. The docker image used to execute the jobs is the one defined in Fargate task difinition. We can override the docker image, by creating a new task definition and set the variable FARGATE_TASK_DEFINITION in `.gitlab-ci.yml`.

![Results](/docs/img/gitlab-pipeline-screenshot.png)
# LICENSE
This project is licensed under the MIT-0 License. See the LICENSE file.

