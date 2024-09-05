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

import os
import uuid
from typing import Any, Dict
import shlex

import boto3
from botocore.exceptions import ClientError

user_data_template = """#! /bin/bash -ex

(r=5;while ! yum install -y docker ; do ((--r))||exit;sleep 60;done)
systemctl start docker
mkdir /home/ec2-user/docker_resources
aws s3 sync s3://{{BUCKET_NAME}} /home/ec2-user/docker_resources
cd /home/ec2-user/docker_resources/{{LAYER_TO_ADD}}
docker build -t {{IMAGE_ID}} --build-arg BASE_IMAGE={{BASE_IMAGE}} --build-arg MOUNTS3_DEB_URL={{MOUNTS3_DEB_URL}} .
docker tag {{IMAGE_ID}} {{ECR_URI}}:{{IMAGE_ID}}
aws ecr get-login-password | docker login --username AWS --password-stdin {{ECR_URI}}
docker push {{ECR_URI}}:{{IMAGE_ID}}
"""


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:  # type: ignore [no-untyped-def]
    base_image = event["base_image"]
    layer_to_add = event["layer_to_add"]
    mounts3_deb_url = event["mounts3_deb_url"]

    ec2_resource = boto3.resource("ec2", region_name="us-east-1")

    rendered_userdata = user_data_template
    rendered_userdata = rendered_userdata.replace("{{BUCKET_NAME}}", shlex.quote(os.environ["LISA_DOCKER_BUCKET"]))
    rendered_userdata = rendered_userdata.replace("{{LAYER_TO_ADD}}", shlex.quote(layer_to_add))
    rendered_userdata = rendered_userdata.replace("{{BASE_IMAGE}}", shlex.quote(base_image))
    rendered_userdata = rendered_userdata.replace("{{MOUNTS3_DEB_URL}}", shlex.quote(mounts3_deb_url))
    rendered_userdata = rendered_userdata.replace("{{ECR_URI}}", shlex.quote(os.environ["LISA_ECR_URI"]))
    rendered_userdata = rendered_userdata.replace("{{IMAGE_ID}}", str(uuid.uuid4()))

    print("Creating instance with userdata: ")
    print(rendered_userdata)
    try:
        ec2_resource.create_instances(
            ImageId="ami-066784287e358dad1",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.medium",
            UserData=rendered_userdata,
            IamInstanceProfile={"Arn": os.environ["LISA_INSTANCE_PROFILE"]},
            BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 32}}],
        )
    except ClientError as e:
        print(e)
        pass
