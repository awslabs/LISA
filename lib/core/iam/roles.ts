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

export const ROLE = 'Role';

/**
 * List of all roles used for overrides with their corresponding RoleId
 */
export enum Roles {
    DOCKER_IMAGE_BUILDER_DEPLOYMENT_ROLE = 'DockerImageBuilderDeploymentRole',
    DOCKER_IMAGE_BUILDER_EC2_ROLE = 'DockerImageBuilderEC2Role',
    DOCKER_IMAGE_BUILDER_ROLE = 'DockerImageBuilderRole',
    DOCS_DEPLOYER_ROLE = 'DocsDeployerRole',
    DOCS_ROLE = 'DocsRole',
    ECS_MODEL_DEPLOYER_ROLE = 'ECSModelDeployerRole',
    ECS_MODEL_TASK_ROLE = 'ECSModelTaskRole',
    ECS_REST_API_EX_ROLE = 'ECSRestApiExRole',
    ECS_MCPWORKBENCH_API_EX_ROLE = 'ECSMcpWorkbenchApiExRole',
    ECS_REST_API_ROLE = 'ECSRestApiRole',
    ECS_MCPWORKBENCH_API_ROLE = 'ECSMcpWorkbenchApiRole',
    LAMBDA_CONFIGURATION_API_EXECUTION_ROLE = 'LambdaConfigurationApiExecutionRole',
    LAMBDA_EXECUTION_ROLE = 'LambdaExecutionRole',
    MCP_SERVER_DEPLOYER_ROLE = 'McpServerDeployerRole',
    MODEL_API_ROLE = 'ModelApiRole',
    MODEL_SFN_LAMBDA_ROLE = 'ModelsSfnLambdaRole',
    MODEL_SFN_ROLE = 'ModelSfnRole',
    RAG_LAMBDA_EXECUTION_ROLE = 'LisaRagLambdaExecutionRole',
    REST_API_AUTHORIZER_ROLE = 'RestApiAuthorizerRole',
    S3_READER_ROLE = 'S3ReaderRole',
    UI_DEPLOYMENT_ROLE = 'UIDeploymentRole',
    VECTOR_STORE_CREATOR_ROLE = 'VectorStoreCreatorRole'
}

/**
 * This is the RoleName used with roles, which can differ from the RoleNameId. This represents the existing deployed names for backwards compatibility.
 */
export const RoleNames: Record<Roles, string> = {
    [Roles.DOCKER_IMAGE_BUILDER_DEPLOYMENT_ROLE]: 'DockerImageBuilderDeploymentRole',
    [Roles.DOCKER_IMAGE_BUILDER_EC2_ROLE]: 'DockerImageBuilderEC2Role',
    [Roles.DOCKER_IMAGE_BUILDER_ROLE]: 'DockerImageBuilderRole',
    [Roles.DOCS_DEPLOYER_ROLE]: 'DocsDeployerRole',
    [Roles.DOCS_ROLE]: 'DocsRole',
    [Roles.ECS_MODEL_DEPLOYER_ROLE]: 'ECSModelDeployerRole',
    [Roles.ECS_MODEL_TASK_ROLE]: 'ECSModelTaskRole',
    [Roles.ECS_REST_API_EX_ROLE]: 'ECSRestApiExRole',
    [Roles.ECS_MCPWORKBENCH_API_EX_ROLE]: 'ECSMcpWorkbenchApiExRole',
    [Roles.ECS_REST_API_ROLE]: 'ECSRestApiRole',
    [Roles.ECS_MCPWORKBENCH_API_ROLE]: 'ECSMcpWorkbenchApiRole',
    [Roles.LAMBDA_CONFIGURATION_API_EXECUTION_ROLE]: 'LambdaConfigurationApiExecutionRole',
    [Roles.LAMBDA_EXECUTION_ROLE]: 'LambdaExecutionRole',
    [Roles.MCP_SERVER_DEPLOYER_ROLE]: 'McpServerDeployerRole',
    [Roles.MODEL_API_ROLE]: 'ModelApiRole',
    [Roles.MODEL_SFN_LAMBDA_ROLE]: 'ModelsSfnLambdaRole',
    [Roles.MODEL_SFN_ROLE]: 'ModelSfnRole',
    [Roles.RAG_LAMBDA_EXECUTION_ROLE]: 'RAGRole',
    [Roles.REST_API_AUTHORIZER_ROLE]: 'RestApiAuthorizerRole',
    [Roles.S3_READER_ROLE]: 'S3ReaderRole',
    [Roles.UI_DEPLOYMENT_ROLE]: 'UIDeploymentRole',
    [Roles.VECTOR_STORE_CREATOR_ROLE]: 'VectorStoreCreatorRole',
};

export function getRoleId (key: string): Roles {
    const keys = Object.keys(Roles).filter((x) => x === key);
    if (keys.length > 0)
        return Roles[keys[0] as keyof typeof Roles] as Roles;
    else {
        throw Error(`No Roles entry exists for ${key}`);
    }
}
