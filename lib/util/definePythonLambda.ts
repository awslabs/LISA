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

import { Duration } from 'aws-cdk-lib';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { IRole } from 'aws-cdk-lib/aws-iam';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

import { getPythonRuntime } from '../api-base/utils';
import { Vpc } from '../networking/vpc';
import { Config } from '../schema';
import { LambdaHandler, lambdaCodeAsset } from './lambdaCode';
import { getLisaSharedLayer } from './lambdaLayers';

/** Options accepted by {@link definePythonLambda}. */
export type DefinePythonLambdaProps = {
    /** Handler package under `lambda/handlers/`. The directory is zipped as the function's code asset. */
    handlerDir: LambdaHandler;
    /**
     * Dotted path to the Python entry point, relative to the root of the
     * handler asset. Do NOT prefix with the handler directory name.
     * Examples:
     *  - `lambda_functions.handler`
     *  - `state_machine.create_model.handle_failure`
     *  - `handler.main`
     */
    entry: string;
    /** LISA deployment config. Used for `lambdaPath` zip fallback and layer resolution. */
    config: Config;
    /**
     * Third-party Lambda layers to attach. The `LisaSharedLayer` is
     * auto-attached (and de-duplicated per scope) so callers never need
     * to include the shared first-party source layer here.
     */
    layers?: ILayerVersion[];
    /** Override the asset if the function ships as a prebuilt zip or other Code. */
    codeOverride?: Code;
    environment?: Record<string, string>;
    role?: IRole;
    vpc?: Vpc;
    securityGroups?: ISecurityGroup[];
    timeout?: Duration;
    memorySize?: number;
    description?: string;
    reservedConcurrentExecutions?: number;
    functionName?: string;
    logRetention?: RetentionDays;
};

/**
 * Creates a Python Lambda function with LISA's standard defaults applied.
 * Thin wrapper over `new Function(...)` that:
 *   - Resolves the handler asset via {@link lambdaCodeAsset}.
 *   - Auto-attaches the `LisaSharedLayer` so every handler can `import lisa.*`.
 *   - Applies the LISA default runtime, timeout (180s), and memory (512 MiB).
 *   - Wires the optional VPC + subnets in a single place.
 */
export function definePythonLambda (scope: Construct, id: string, props: DefinePythonLambdaProps): Function {
    return new Function(scope, id, {
        functionName: props.functionName,
        runtime: getPythonRuntime(),
        handler: props.entry,
        code: props.codeOverride ?? lambdaCodeAsset(props.handlerDir, props.config),
        description: props.description,
        environment: props.environment,
        timeout: props.timeout ?? Duration.seconds(180),
        memorySize: props.memorySize ?? 512,
        layers: [getLisaSharedLayer(scope, props.config), ...(props.layers ?? [])],
        role: props.role,
        vpc: props.vpc?.vpc,
        vpcSubnets: props.vpc?.subnetSelection,
        securityGroups: props.securityGroups,
        reservedConcurrentExecutions: props.reservedConcurrentExecutions,
        logRetention: props.logRetention,
    });
}
