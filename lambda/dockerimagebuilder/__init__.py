#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import logging
import os
import shlex
import uuid
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

user_data_template = """#! /bin/bash -ex

export AWS_REGION={{AWS_REGION}}
export LOG_GROUP={{LOG_GROUP}}

# Install CloudWatch agent and docker
(r=5;while ! yum install -y docker amazon-cloudwatch-agent ; do ((--r))||exit;sleep 60;done)

# Configure CloudWatch agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/docker-build.log",
            "log_group_name": "${LOG_GROUP}",
            "log_stream_name": "docker-build-{{IMAGE_ID}}"
          }
        ]
      }
    }
  }
}
EOF

# Start services
systemctl start docker

# Start CloudWatch agent with configuration
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \\
    -a fetch-config -m ec2 \\
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# Setup build environment
mkdir /home/ec2-user/docker_resources
aws --region ${AWS_REGION} s3 sync s3://{{BUCKET_NAME}} /home/ec2-user/docker_resources
cd /home/ec2-user/docker_resources/{{LAYER_TO_ADD}}

while [ 1 ]; do
    shutdown -c;
    sleep 5;
done &

function buildTagPush() {
    echo "Starting Docker build for {{IMAGE_ID}}" | tee -a /var/log/docker-build.log
    sed -iE 's/^FROM.*/FROM {{BASE_IMAGE}}/' Dockerfile
    docker build -t {{IMAGE_ID}} --build-arg BASE_IMAGE={{BASE_IMAGE}} \\
        --build-arg MOUNTS3_DEB_URL={{MOUNTS3_DEB_URL}} . 2>&1 | tee -a /var/log/docker-build.log && \\
    docker tag {{IMAGE_ID}} {{ECR_URI}}:{{IMAGE_ID}} 2>&1 | tee -a /var/log/docker-build.log && \\
    aws --region ${AWS_REGION} ecr get-login-password | \\
        docker login --username AWS --password-stdin {{ECR_URI}} 2>&1 | tee -a /var/log/docker-build.log && \\
    docker push {{ECR_URI}}:{{IMAGE_ID}} 2>&1 | tee -a /var/log/docker-build.log
    echo "Build completed with exit code $?" | tee -a /var/log/docker-build.log
    return $?
}

(r=3;while ! buildTagPush ; do ((--r))||exit;sleep 10; done)
"""


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:  # type: ignore [no-untyped-def]
    logger.info(f"Starting Docker image builder with event: {event}")

    base_image = event["base_image"]
    layer_to_add = event["layer_to_add"]
    mounts3_deb_url = os.environ["LISA_MOUNTS3_DEB_URL"]

    logger.info(f"Building image with base: {base_image}, layer: {layer_to_add}")

    ec2_resource = boto3.resource("ec2", region_name=os.environ["AWS_REGION"])
    ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])

    response = ssm_client.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")
    ami_id = response["Parameter"]["Value"]
    image_tag = str(uuid.uuid4())

    logger.info(f"Using AMI: {ami_id}, Image tag: {image_tag}")

    rendered_userdata = user_data_template
    rendered_userdata = rendered_userdata.replace("{{AWS_REGION}}", shlex.quote(os.environ["AWS_REGION"]))
    rendered_userdata = rendered_userdata.replace("{{LOG_GROUP}}", shlex.quote(context.log_group_name))
    rendered_userdata = rendered_userdata.replace("{{BUCKET_NAME}}", shlex.quote(os.environ["LISA_DOCKER_BUCKET"]))
    rendered_userdata = rendered_userdata.replace("{{LAYER_TO_ADD}}", shlex.quote(layer_to_add))
    rendered_userdata = rendered_userdata.replace("{{BASE_IMAGE}}", shlex.quote(base_image))
    rendered_userdata = rendered_userdata.replace("{{MOUNTS3_DEB_URL}}", shlex.quote(mounts3_deb_url))
    rendered_userdata = rendered_userdata.replace("{{ECR_URI}}", shlex.quote(os.environ["LISA_ECR_URI"]))
    rendered_userdata = rendered_userdata.replace("{{IMAGE_ID}}", image_tag)

    try:
        # Define common parameters
        instance_params = {
            "ImageId": ami_id,
            "MinCount": 1,
            "MaxCount": 1,
            "InstanceType": "m5.large",
            "UserData": rendered_userdata,
            "IamInstanceProfile": {"Arn": os.environ["LISA_INSTANCE_PROFILE"]},
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "VolumeSize": int(os.environ["LISA_IMAGEBUILDER_VOLUME_SIZE"]),
                        "Encrypted": True,
                    },
                }
            ],
            "TagSpecifications": [
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": f"LisaDockerImageBuilder_{image_tag}"},
                        {"Key": "lisa_temporary_instance", "Value": "true"},
                    ],
                }
            ],
        }

        # Add SubnetId if specified in environment
        if "LISA_SUBNET_ID" in os.environ:
            instance_params["SubnetId"] = os.environ["LISA_SUBNET_ID"]

        # Create instance with parameters
        logger.info(f"Creating Builder EC2 instance with params: {instance_params}")
        instances = ec2_resource.create_instances(**instance_params)

        instance_id = instances[0].instance_id
        logger.info(f"Successfully created Builder EC2 instance: {instance_id}")

        return {"instance_id": instance_id, "image_tag": image_tag}

    except ClientError as e:
        logger.error(f"Failed to create EC2 instance: {str(e)}")
        raise e
