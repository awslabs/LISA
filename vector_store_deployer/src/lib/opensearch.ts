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
import { CustomResource, Duration, StackProps } from 'aws-cdk-lib';
import { Domain, EngineVersion, IDomain } from 'aws-cdk-lib/aws-opensearchservice';
import { Construct } from 'constructs';
import { RagRepositoryDeploymentConfig, RagRepositoryType,PartialConfig } from '../../../lib/schema';
import { SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';
import { AnyPrincipal, Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { createCdkId } from '../../../lib/core/utils';
import { Roles } from '../../../lib/core/iam/roles';
import { PipelineStack } from './pipeline-stack';
import { Code, Function } from 'aws-cdk-lib/aws-lambda';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { getPythonRuntime } from '../../../lib/api-base/utils';

type OpenSearchVectorStoreStackProps = StackProps & {
    config: PartialConfig
    ragConfig: RagRepositoryDeploymentConfig,
};

export class OpenSearchVectorStoreStack extends PipelineStack {
    constructor (scope: Construct, id: string, props: OpenSearchVectorStoreStackProps) {
        super(scope, id, props);

        const { config, ragConfig } = props;
        const { vpcId, deploymentName, deploymentPrefix, deploymentStage, subnets} = config;
        const { repositoryId, opensearchConfig } = ragConfig;

        // Create service-linked role conditionally - only if it doesn't already exist
        // OpenSearch service-linked roles cannot use custom suffixes, so we must check for existence
        const serviceLinkedRoleLambda = new Function(this, 'OpensearchServiceLinkedRoleLambda', {
            runtime: getPythonRuntime(),
            handler: 'index.handler',
            code: Code.fromInline(`
import boto3
import cfnresponse
from botocore.exceptions import ClientError

def handler(event, context):
    iam = boto3.client('iam')
    service_name = 'opensearchservice.amazonaws.com'

    try:
        if event['RequestType'] == 'Delete':
            # Don't delete service-linked roles on stack deletion
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return

        # Check if the service-linked role already exists
        try:
            roles = iam.list_roles(PathPrefix='/aws-service-role/opensearchservice.amazonaws.com/')
            if roles.get('Roles') and len(roles['Roles']) > 0:
                # Role already exists, return success
                role = roles['Roles'][0]
                print(f"Service-linked role already exists: {role['RoleName']}")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                    'RoleArn': role['Arn'],
                    'RoleName': role['RoleName']
                })
                return
        except Exception as e:
            print(f"Error listing roles: {str(e)}")
            pass

        # Role doesn't exist, create it
        try:
            response = iam.create_service_linked_role(AWSServiceName=service_name)
            print(f"Created service-linked role: {response['Role']['RoleName']}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'RoleArn': response['Role']['Arn'],
                'RoleName': response['Role']['RoleName']
            })
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e)
            if error_code == 'InvalidInput' and ('has been taken' in error_message or 'already exists' in error_message.lower()):
                # Role was created between our check and creation attempt
                try:
                    roles = iam.list_roles(PathPrefix='/aws-service-role/opensearchservice.amazonaws.com/')
                    if roles.get('Roles') and len(roles['Roles']) > 0:
                        role = roles['Roles'][0]
                        print(f"Service-linked role was created concurrently: {role['RoleName']}")
                        cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                            'RoleArn': role['Arn'],
                            'RoleName': role['RoleName']
                        })
                        return
                except Exception as list_error:
                    print(f"Error listing roles after creation conflict: {str(list_error)}")
            # Re-raise if we can't handle it
            raise

    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
`),
            timeout: Duration.seconds(30),
            description: 'Conditionally creates OpenSearch service-linked role if it does not exist',
        });

        // Grant IAM permissions to the Lambda
        serviceLinkedRoleLambda.addToRolePolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'iam:ListRoles',
                'iam:CreateServiceLinkedRole',
            ],
            resources: ['*'],
        }));

        const serviceLinkedRoleProvider = new Provider(this, 'OpensearchServiceLinkedRoleProvider', {
            onEventHandler: serviceLinkedRoleLambda,
        });

        const serviceLinkedRole = new CustomResource(this, 'OpensearchServiceLinkedRole', {
            serviceToken: serviceLinkedRoleProvider.serviceToken,
            properties: {
                ServiceName: 'opensearchservice.amazonaws.com',
            },
        });

        let openSearchDomain: IDomain;

        if (opensearchConfig === undefined) {
            return;
        }

        const vpc = Vpc.fromLookup(this, 'Vpc', {
            vpcId,
            returnVpnGateways: false,
        });

        let subnetSelection: SubnetSelection | undefined;

        if (subnets && subnets.length > 0) {
            subnetSelection = {
                subnets: props.config.subnets?.map((subnet, index) => Subnet.fromSubnetAttributes(this, index.toString(), {
                    subnetId: subnet.subnetId,
                    ipv4CidrBlock: subnet.ipv4CidrBlock,
                    availabilityZone: subnet.availabilityZone
                }))
            };
        }

        if ('endpoint' in opensearchConfig) {
            openSearchDomain = Domain.fromDomainEndpoint(
                this,
                'ExistingOpenSearchDomain',
                opensearchConfig.endpoint,
            );
        } else {
            // Create security group from ID stored in SSM parameter
            const securityGroupId = StringParameter.valueFromLookup(this, `${config.deploymentPrefix}/openSearchSecurityGroupId`);
            const openSearchSecurityGroup = SecurityGroup.fromSecurityGroupId(
                this,
                'OpenSearchSecurityGroup',
                securityGroupId
            );

            openSearchDomain = new Domain(this, createCdkId([deploymentName!, deploymentStage!, 'RagRepository', repositoryId]), {
                domainName: ['lisa-rag', repositoryId].join('-'),
                // 2.9 is the latest available in ADC regions as of 1/11/24
                version: EngineVersion.OPENSEARCH_2_9,
                enableVersionUpgrade: true,
                vpc: vpc,
                ...(subnetSelection && {vpcSubnets: [subnetSelection]}),
                ebs: {
                    enabled: true,
                    volumeSize: opensearchConfig.volumeSize,
                    volumeType: opensearchConfig.volumeType,
                },
                zoneAwareness: {
                    availabilityZoneCount: (config.subnets && config.subnets.length) ?? vpc.privateSubnets.length,
                    enabled: true,
                },
                capacity: {
                    dataNodes: opensearchConfig.dataNodes,
                    dataNodeInstanceType: opensearchConfig.dataNodeInstanceType,
                    masterNodes: opensearchConfig.masterNodes,
                    masterNodeInstanceType: opensearchConfig.masterNodeInstanceType,
                    multiAzWithStandbyEnabled: opensearchConfig.multiAzWithStandby,
                },
                accessPolicies: [
                    new PolicyStatement({
                        actions: ['es:*'],
                        resources: ['*'],
                        effect: Effect.ALLOW,
                        principals: [new AnyPrincipal()],
                    }),
                ],
                nodeToNodeEncryption: true,
                enforceHttps: true,
                encryptionAtRest: {
                    enabled: true
                },
                removalPolicy: config.removalPolicy,
                securityGroups: [openSearchSecurityGroup],
            });

            // Ensure service-linked role is created before OpenSearch domain
            openSearchDomain.node.addDependency(serviceLinkedRole);
        }

        const lambdaRole = Role.fromRoleArn(
            this,
            `${Roles.RAG_LAMBDA_EXECUTION_ROLE}-${repositoryId}`,
            StringParameter.valueForStringParameter(
                this,
                `${deploymentPrefix}/roles/${createCdkId([deploymentName!, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Rag API task execution role will read and write
        openSearchDomain.grantIndexReadWrite('*', lambdaRole);
        openSearchDomain.grantPathReadWrite('*', lambdaRole);
        openSearchDomain.grantReadWrite(lambdaRole);

        const configParam = {type: RagRepositoryType.OPENSEARCH, endpoint: openSearchDomain.domainEndpoint };
        const openSearchEndpointPs = new StringParameter(
            this,
            createCdkId([repositoryId, 'StringParameter']),
            {
                parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${repositoryId}`,
                stringValue: JSON.stringify(configParam),
                description: 'Endpoint for LISA Serve OpenSearch Rag Repository',
            },
        );

        // Add explicit dependency on OpenSearch Domain being created
        openSearchEndpointPs.grantRead(lambdaRole);

        this.createPipelineRules(config, ragConfig);
    }
}
