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
import { StackProps, Duration, Size, CfnOutput } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { createCdkId, pickFields } from '../../core/utils';
import { BaseProps } from '../../schema';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Vpc } from '../../networking/vpc';
import { CreateStoreStateMachine } from './state_machine/create-store';
import { DeleteStoreStateMachine } from './state_machine/delete-store';
import { Roles } from '../../core/iam/roles';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { ILayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { CodeFactory, VECTOR_STORE_DEPLOYER_DIST_PATH } from '../../util';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';

export type VectorStoreCreatorStackProps = StackProps & BaseProps & {
    ragVectorStoreTable: CfnOutput;
    vpc: Vpc;
    baseEnvironment: Record<string, string>
    layers: ILayerVersion[],
};

// Main stack that contains the Lambda function
export class VectorStoreCreatorStack extends Construct {
    readonly vectorStoreCreatorFn: lambda.IFunction;

    constructor (scope: Construct, id: string, props: VectorStoreCreatorStackProps) {
        super(scope, id);

        const { baseEnvironment, config, layers, ragVectorStoreTable, vpc } = props;

        const vectorStoreTable = dynamodb.Table.fromTableArn(this, createCdkId([config.deploymentPrefix, 'RagVectorStoreTable']), ragVectorStoreTable.value);

        // Create Lambda role with permissions to create CloudFormation stacks
        const cdkRole = new iam.Role(this, `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.VECTOR_STORE_CREATOR_ROLE])}`, {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.fromAwsManagedPolicyName('AWSCloudFormationFullAccess'),
            ],
        });

        // Additional CloudFormation permissions that might be needed
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'cloudformation:ValidateTemplate',
                'cloudformation:EstimateTemplateCost',
                'cloudformation:ListStacks',
                'cloudformation:ListStackResources'
            ],
            resources: ['*'],
        }));

        const lambdaExecutionRole = iam.Role.fromRoleArn(
            this,
            `${Roles.RAG_LAMBDA_EXECUTION_ROLE}-VectorStore`,
            ssm.StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Add least-privilege permissions for resources created by dynamic stacks
        // S3: CDK asset bucket access
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['s3:PutObject', 's3:GetObject', 's3:DeleteObject', 's3:ListBucket'],
            resources: ['*'],
        }));

        // SSM: comprehensive read/write permissions for deployment parameters
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['ssm:GetParameter', 'ssm:GetParameters', 'ssm:GetParametersByPath', 'ssm:PutParameter'],
            resources: ['*'],
        }));

        // IAM: service-linked role creation for required services
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:CreateServiceLinkedRole'],
            resources: ['*'],
            conditions: {
                StringEquals: {
                    'iam:AWSServiceName': ['opensearchservice.amazonaws.com', 'rds.amazonaws.com']
                }
            }
        }));

        // IAM: manage roles created within the dynamic stacks and allow passing to services
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'iam:CreateRole',
                'iam:DeleteRole',
                'iam:AttachRolePolicy',
                'iam:DetachRolePolicy',
                'iam:PutRolePolicy',
                'iam:DeleteRolePolicy',
                'iam:TagRole',
                'iam:UntagRole',
                'iam:GetRole',
                'iam:GetRolePolicy',
                'iam:ListRolePolicies',
                'iam:ListAttachedRolePolicies',
                'iam:GetRolePolicy',
                'iam:ListRoleTags',
                'iam:UpdateAssumeRolePolicy'
            ],
            resources: ['*'],
        }));
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: ['iam:PassRole'],
            resources: ['*'],
            conditions: {
                StringEquals: {
                    'iam:PassedToService': [
                        'lambda.amazonaws.com',
                        'events.amazonaws.com'
                    ]
                }
            }
        }));

        // EC2: VPC networking for Lambdas/DB and SG updates
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'ec2:DescribeVpcs',
                'ec2:DescribeSubnets',
                'ec2:DescribeSecurityGroups',
                'ec2:DescribeRouteTables',
                'ec2:DescribeInternetGateways',
                'ec2:DescribeNatGateways',
                'ec2:DescribeVpcEndpoints',
                'ec2:DescribeVpcPeeringConnections',
                'ec2:DescribeNetworkAcls',
                'ec2:DescribeAvailabilityZones',
                'ec2:DescribeAccountAttributes',
                'ec2:DescribeVpnGateways',
                'ec2:DescribeVpnConnections',
                'ec2:DescribeVpcAttribute',
                'ec2:DescribeVpcClassicLink',
                'ec2:DescribeVpcClassicLinkDnsSupport',
                'ec2:CreateNetworkInterface',
                'ec2:DeleteNetworkInterface',
                'ec2:DescribeNetworkInterfaces',
                'ec2:AuthorizeSecurityGroupIngress',
                'ec2:RevokeSecurityGroupIngress'
            ],
            resources: ['*'],
        }));

        // RDS: lifecycle for PGVector DBs
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'rds:CreateDBInstance',
                'rds:DeleteDBInstance',
                'rds:ModifyDBInstance',
                'rds:DescribeDBInstances',
                'rds:AddTagsToResource',
                'rds:ListTagsForResource',
                'rds:RemoveTagsFromResource'
            ],
            resources: ['*'],
        }));

        // Secrets Manager: credentials for databases
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'secretsmanager:CreateSecret',
                'secretsmanager:PutSecretValue',
                'secretsmanager:GetSecretValue',
                'secretsmanager:DescribeSecret',
                'secretsmanager:TagResource',
                'secretsmanager:UntagResource',
                'secretsmanager:DeleteSecret'
            ],
            resources: ['*'],
        }));

        // EventBridge: rules for pipelines
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'events:PutRule',
                'events:PutTargets',
                'events:DeleteRule',
                'events:RemoveTargets',
                'events:ListTargetsByRule'
            ],
            resources: ['*'],
        }));

        // Lambda: helper/custom resource functions created by dynamic stacks
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'lambda:CreateFunction',
                'lambda:UpdateFunctionCode',
                'lambda:UpdateFunctionConfiguration',
                'lambda:DeleteFunction',
                'lambda:AddPermission',
                'lambda:RemovePermission',
                'lambda:GetFunction',
                'lambda:TagResource',
                'lambda:UntagResource'
            ],
            resources: ['*'],
        }));

        // OpenSearch: restrict to domains created by LISA naming
        cdkRole.addToPolicy(new iam.PolicyStatement({
            actions: [
                'es:CreateDomain',
                'es:DeleteDomain',
                'es:DescribeDomain',
                'es:DescribeDomains',
                'es:UpdateDomainConfig',
                'es:AddTags',
                'es:RemoveTags'
            ],
            resources: [`arn:${config.partition}:es:${config.region}:${config.accountNumber}:domain/lisa-rag-*`],
        }));

        const stateMachineRole = new iam.Role(this, createCdkId([config.deploymentName, config.deploymentStage, 'StateMachineRole']), {
            assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
        });
        vectorStoreTable.grantReadWriteData(stateMachineRole);

        // create a stripped down config to store only the fields we care about
        const strippedConfig = {
            ...pickFields(props.config, [
                'accountNumber',
                'appName',
                'deploymentName',
                'deploymentStage',
                'deploymentPrefix',
                'partition',
                'region',
                'removalPolicy',
                'subnets',
                'profile',
                'vpcId',
            ]),
            ...(vpc.vpc.vpcId && { vpcId: vpc.vpc.vpcId })
        };

        const functionId = createCdkId([props.config.deploymentName, props.config.deploymentStage, 'vector_store_deployer', 'Fn']);
        const vectorStoreDeployer = config.vectorStoreDeployerPath || VECTOR_STORE_DEPLOYER_DIST_PATH;
        this.vectorStoreCreatorFn = new NodejsFunction(this, functionId, {
            functionName: functionId,
            code: CodeFactory.createCode(vectorStoreDeployer),
            timeout: Duration.minutes(15),
            ephemeralStorageSize: Size.mebibytes(2048),
            runtime: Runtime.NODEJS_18_X,
            handler: 'index.handler',
            memorySize: 1024,
            role: cdkRole,
            environment: {
                'LISA_CONFIG': JSON.stringify(strippedConfig),
                'LISA_RAG_VECTOR_STORE_TABLE': vectorStoreTable.tableName
            },
            vpcSubnets: vpc.subnetSelection,
            vpc: props.vpc.vpc,
            securityGroups: [props.vpc.securityGroups.lambdaSg],
        });

        // Allow the state machine to invoke the deployer Lambda
        this.vectorStoreCreatorFn.grantInvoke(stateMachineRole);

        // Minimal policies for state machine role
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['lambda:InvokeFunction'],
            resources: [this.vectorStoreCreatorFn.functionArn],
        }));
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['cloudformation:DescribeStacks', 'cloudformation:DeleteStack'],
            resources: ['*'],
        }));
        stateMachineRole.addToPolicy(new iam.PolicyStatement({
            actions: ['dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:GetItem', 'dynamodb:DeleteItem'],
            resources: [vectorStoreTable.tableArn],
        }));

        new CreateStoreStateMachine(this, 'CreateVectorStoreStateMachine', {
            config: props.config,
            executionRole: lambdaExecutionRole,
            parameterName: baseEnvironment['LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER'],
            role: stateMachineRole,
            vectorStoreConfigTable: vectorStoreTable,
            vectorStoreDeployerFnArn: this.vectorStoreCreatorFn.functionArn,
            vpc: props.vpc,
        });

        new DeleteStoreStateMachine(this, 'DeleteStoreStateMachine', {
            config: props.config,
            executionRole: lambdaExecutionRole,
            lambdaLayers: layers,
            parameterName: baseEnvironment['LISA_RAG_DELETE_STATE_MACHINE_ARN_PARAMETER'],
            role: stateMachineRole,
            ragVectorStoreTable: vectorStoreTable,
            vectorStoreDeployerFnArn: this.vectorStoreCreatorFn.functionArn,
            vpc: props.vpc,
            environment: baseEnvironment
        });
    }
}
