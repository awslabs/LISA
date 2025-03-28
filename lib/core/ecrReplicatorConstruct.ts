/**
  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

  Licensed under the Apache License, Version 2.0 (the "License").
  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
*/

import { RemovalPolicy } from 'aws-cdk-lib';
import { Repository, RepositoryEncryption } from 'aws-cdk-lib/aws-ecr';
import { DockerImageAsset } from 'aws-cdk-lib/aws-ecr-assets';
import { ECRDeployment, DockerImageName } from 'cdk-ecr-deployment';
import { Construct } from 'constructs';

export type EcrReplicatorProps = {
    path: string;
    buildArgs?: { [key: string]: string };
};

export class EcrReplicatorConstruct extends Construct {
    constructor (scope: Construct, id: string, props: EcrReplicatorProps) {
        super(scope, id);
        const { path, buildArgs } = props;

        const repo = new Repository(this, `${id}Repo`, {
            repositoryName: `${id}Repo`.toLowerCase(),
            imageScanOnPush: true,
            encryption: RepositoryEncryption.KMS,
            removalPolicy: RemovalPolicy.DESTROY,
            autoDeleteImages: true
        });
        const image = new DockerImageAsset(this, `${id}Image`, {
            directory: path,
            buildArgs
        });
        new ECRDeployment(this, `${id}DeploymentImage`, {
            src: new DockerImageName(image.imageUri),
            dest: new DockerImageName(`${repo.repositoryUri}`),
        });
    }

}
