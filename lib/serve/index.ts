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
import { Stack } from 'aws-cdk-lib';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import { FastApiContainer } from '../api-base/fastApiContainer';
import { LisaServeApplicationConstruct, LisaServeApplicationProps } from './serveApplicationConstruct';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
export * from './serveApplicationConstruct';

/**
 * LisaServe Application stack.
 */
export class LisaServeApplicationStack extends Stack {
    /** FastAPI construct */
    public readonly restApi: FastApiContainer;
    public readonly modelsPs: StringParameter;
    public readonly endpointUrl: StringParameter;
    public readonly tokenTable?: ITable;

    /**
    * @param {Construct} scope - The parent or owner of the construct.
    * @param {string} id - The unique identifier for the construct within its scope.
    * @param {LisaServeApplicationProps} props - Properties for the Stack.
    */
    constructor (scope: Construct, id: string, props: LisaServeApplicationProps) {
        super(scope, id, props);

        const app = new LisaServeApplicationConstruct(this, id + 'Resources', props);
        app.node.addMetadata('aws:cdk:path', this.node.path);
        this.endpointUrl = app.endpointUrl;
        this.modelsPs = app.modelsPs;
        this.restApi = app.restApi;
        this.tokenTable = app.tokenTable;
    }
}
