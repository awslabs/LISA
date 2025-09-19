
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

import { Code, DockerImageCode } from 'aws-cdk-lib/aws-lambda';
import { EcsSourceType, ImageAsset } from '../schema';
import { Repository } from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';
import { ContainerImage } from 'aws-cdk-lib/aws-ecs';
import { createCdkId } from '../core/utils';

export class CodeFactory {
    static createImage (image: ImageAsset, scope?: Construct, id?: string, buildArgs?: any): ContainerImage {
        switch (image.type) {
            case EcsSourceType.ECR: {
                if (!scope || !id) {
                    throw new Error('Scope and id must be provided for ECR image');
                }
                const repository = Repository.fromRepositoryArn(
                    scope,
                    createCdkId([id, 'Repo']),
                    image.repositoryArn,
                );
                return ContainerImage.fromEcrRepository(repository, image.tag);
            }
            case EcsSourceType.REGISTRY: {
                return ContainerImage.fromRegistry(image.registry);
            }
            case EcsSourceType.TARBALL: {
                return ContainerImage.fromTarball(image.path);
            }
            case EcsSourceType.EXTERNAL: {
                return image.code;
            }
            case EcsSourceType.ASSET:
            default: {
                return ContainerImage.fromAsset(image.path, { buildArgs });
            }
        }
    }

    static createDockerImageCode (image: ImageAsset | string, buildArgs?: any): DockerImageCode {
        if (typeof image === 'string') {
            return DockerImageCode.fromImageAsset(image, { buildArgs, exclude: ['cdk.out'] });
        }

        switch (image.type) {
            case EcsSourceType.EXTERNAL:
                return image.code;
            case EcsSourceType.ASSET:
                return DockerImageCode.fromImageAsset(image.path, { buildArgs, exclude: ['cdk.out'] });
            default:
                throw Error(`Unimplemented image type for DockerImageCode: ${image.type}`);
        }
    }

    static createCode (image: ImageAsset | string, scope?: Construct, id?: string): Code {
        if (typeof image === 'string') {
            return Code.fromAsset(image);
        }

        switch (image.type) {
            case EcsSourceType.EXTERNAL:
                return image.code;
            case EcsSourceType.ECR: {
                if (!scope || !id) {
                    throw new Error('Scope and id must be provided for ECR image');
                }
                const repository = Repository.fromRepositoryArn(
                    scope,
                    createCdkId([id, 'Repo']),
                    image.repositoryArn,
                );
                return Code.fromEcrImage(repository);
            }
            case EcsSourceType.REGISTRY:
                throw new Error('Unsupported Code Source');
            case EcsSourceType.TARBALL:
            case EcsSourceType.ASSET:
            default: {
                return Code.fromAsset(image.path);
            }
        }
    }
}
