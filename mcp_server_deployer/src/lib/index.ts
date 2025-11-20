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

import { App, Aspects } from 'aws-cdk-lib';
import { AddPermissionBoundary } from '@cdklabs/cdk-enterprise-iac';
import { PartialConfigSchema } from '../../../lib/schema';
import { LisaMcpStack } from './lisa-mcp-stack';
import { McpServerConfig } from './utils';

const app = new App();

console.log(`LISA_CONFIG = ${process.env['LISA_CONFIG']}`);
const config = PartialConfigSchema.parse(JSON.parse(process.env['LISA_CONFIG']!));

if (!process.env['LISA_MCP_SERVER_CONFIG']) {
    throw new Error('LISA_MCP_SERVER_CONFIG environment variable not set');
}
const mcpServerConfig: McpServerConfig = JSON.parse(process.env['LISA_MCP_SERVER_CONFIG']!);

if (!process.env['LISA_VPC_ID']) {
    throw new Error('LISA_VPC_ID environment variable not set');
}
const vpcId = process.env['LISA_VPC_ID']!;

if (!process.env['LISA_SECURITY_GROUP_ID']) {
    throw new Error('LISA_SECURITY_GROUP_ID environment variable not set');
}
const securityGroupId = process.env['LISA_SECURITY_GROUP_ID']!;

const stackName = process.env['LISA_STACK_NAME'];
console.log(`Using stack name: ${stackName}`);

// API Gateway environment variables (optional)
const restApiId = process.env['LISA_REST_API_ID'];
const rootResourceId = process.env['LISA_ROOT_RESOURCE_ID'];
const mcpResourceId = process.env['LISA_MCP_RESOURCE_ID'];

const mcpServerProps = {
    config,
    mcpServerConfig,
    vpcId,
    securityGroupId,
    restApiId,
    rootResourceId,
    mcpResourceId,
    env: {
        account: process.env['CDK_DEFAULT_ACCOUNT'],
        region: process.env['CDK_DEFAULT_REGION'],
    },
};

const stack = new LisaMcpStack(app, stackName!, mcpServerProps);

if (config.permissionsBoundaryAspect) {
    Aspects.of(stack).add(new AddPermissionBoundary(config.permissionsBoundaryAspect!));
}

app.synth();
