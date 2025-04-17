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
import { Authorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';
import { LisaApiBaseConstruct, LisaApiBaseProps } from './apiBaseConstruct';

/**
 * LisaApiBase Stack
 */
export class LisaApiBaseStack extends Stack {
    public readonly restApi: RestApi;
    public readonly authorizer?: Authorizer;
    public readonly restApiId: string;
    public readonly rootResourceId: string;
    public readonly restApiUrl: string;

    constructor (scope: Construct, id: string, props: LisaApiBaseProps) {
        super(scope, id, props);

        const api = new LisaApiBaseConstruct(this, id + 'Resources', props);
        api.node.addMetadata('aws:cdk:path', this.node.path);
        this.authorizer = api.authorizer;
        this.restApi = api.restApi;
        this.restApiId = api.restApi.restApiId;
        this.rootResourceId = api.restApi.restApiRootResourceId;
        this.restApiUrl = api.restApi.url;
    }
}
