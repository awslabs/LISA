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

import { ILayerVersion, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { Config } from '../schema';

/**
 * Layer keys published to SSM by `CoreConstruct`. Each key maps to a single
 * `${deploymentPrefix}/layerVersion/<key>` parameter.
 */
export type LisaLayerKey = 'common' | 'fastapi' | 'authorizer' | 'cdk' | 'lisa-shared' | 'rag';

function importLayer (scope: Construct, config: Config, key: LisaLayerKey, id: string): ILayerVersion {
    const arn = StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/${key}`);
    return LayerVersion.fromLayerVersionArn(scope, id, arn);
}

/**
 * Imports a list of third-party layers from SSM. This does NOT include the
 * `lisa-shared` first-party source layer — that one is auto-attached to
 * every Python Lambda created via `registerAPIEndpoint` or
 * `definePythonLambda` (see `getLisaSharedLayer`). Use this helper to
 * build the extras list cleanly.
 *
 * Use `idPrefix` so the imported CfnParameter tokens are uniquely named
 * within the caller's construct scope.
 */
export function getPythonLambdaLayers (
    scope: Construct,
    config: Config,
    extras: readonly Exclude<LisaLayerKey, 'lisa-shared' | 'cdk'>[],
    idPrefix = 'ImportedLayer',
): ILayerVersion[] {
    return extras.map((key) => importLayer(scope, config, key, `${idPrefix}-${key}`));
}

/**
 * Imports only the shared source layer. Use this when a construct already
 * builds its own `lambdaLayers` array and just needs to append the shared
 * one. The layer is cached per scope via a child-construct lookup so
 * repeated calls within the same construct reuse a single import node.
 */
export function getLisaSharedLayer (scope: Construct, config: Config): ILayerVersion {
    const CACHE_ID = 'LisaSharedLayerImport';
    const existing = scope.node.tryFindChild(CACHE_ID) as ILayerVersion | undefined;
    if (existing) {
        return existing;
    }
    const arn = StringParameter.valueForStringParameter(scope, `${config.deploymentPrefix}/layerVersion/lisa-shared`);
    return LayerVersion.fromLayerVersionArn(scope, CACHE_ID, arn);
}
