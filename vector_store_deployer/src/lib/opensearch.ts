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
import { RemovalPolicy, StackProps } from 'aws-cdk-lib';
import { Domain, EngineVersion, IDomain } from 'aws-cdk-lib/aws-opensearchservice';
import { Construct } from 'constructs';
import { PartialConfigSchema, RagRepositoryConfigSchema } from '../../../lib/schema';
import { z } from 'zod';
import { SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';
import { AnyPrincipal, CfnServiceLinkedRole, Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { createCdkId } from '../../../lib/core/utils';
import { IAMClient, ListRolesCommand } from '@aws-sdk/client-iam';
import { Roles } from '../../../lib/core/iam/roles';
import { PipelineStack } from './pipeline-stack';

type OpenSearchVectorStoreStackProps = StackProps & {
    config: z.infer<typeof PartialConfigSchema>
    ragConfig: z.infer<typeof RagRepositoryConfigSchema>,
};

export class OpenSearchVectorStoreStack extends PipelineStack {
    constructor (scope: Construct, id: string, props: OpenSearchVectorStoreStackProps) {
        super(scope, id, props);

        const { config, ragConfig } = props;
        const { vpcId, deploymentName, deploymentPrefix, deploymentStage, subnets} = config;

        if (config.region) {
            this.linkServiceRole(config.region);
        }

        let openSearchDomain: IDomain;

        if (ragConfig?.opensearchConfig === undefined) {
            return;
        }

        const vpc = Vpc.fromLookup(this, 'Vpc', {
            vpcId
        });

        let subnetSelection: SubnetSelection | undefined;

        if (subnets && subnets.length > 0) {
            subnetSelection = {
                subnets: subnets?.map((subnet, index) => Subnet.fromSubnetId(this, `subnet-${index}`, subnet.subnetId))
            };
        }

        const opensearchConfig = ragConfig.opensearchConfig;

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

            openSearchDomain = new Domain(this, createCdkId([deploymentName!, deploymentStage!, 'RagRepository', ragConfig.repositoryId]), {
                domainName: ['lisa-rag', ragConfig.repositoryId].join('-'),
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
                    availabilityZoneCount: vpc.privateSubnets.length,
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
                removalPolicy: RemovalPolicy.DESTROY,
                securityGroups: [openSearchSecurityGroup],
            });
        }

        const lambdaRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                this,
                `${deploymentPrefix}/roles/${createCdkId([deploymentName!, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Rag API task execution role will read and write
        openSearchDomain.grantIndexReadWrite('*', lambdaRole);
        openSearchDomain.grantPathReadWrite('*', lambdaRole);
        openSearchDomain.grantReadWrite(lambdaRole);

        // new CfnOutput(this, createCdkId(['opensearchRagRepositoryEndpoint', ragConfig.repositoryId]), {
        //     value: openSearchDomain.domainEndpoint,
        // });

        const openSearchEndpointPs = new StringParameter(
            this,
            createCdkId([ragConfig.repositoryId, 'StringParameter']),
            {
                parameterName: `${config.deploymentPrefix}/LisaServeRagConnectionInfo/${ragConfig.repositoryId}`,
                stringValue: openSearchDomain.domainEndpoint,
                description: 'Endpoint for LISA Serve OpenSearch Rag Repository',
            },
        );

        // Add explicit dependency on OpenSearch Domain being created
        // openSearchEndpointPs.node.addDependency(openSearchDomain);
        openSearchEndpointPs.grantRead(lambdaRole);
    }

    /**
     * This method links the OpenSearch Service role to the service-linked role if it exists.
     * If the role doesn't exist, it will be created.
     */
    async linkServiceRole (region: string) {
        const iam = new IAMClient({region});
        const response = await iam.send(
            new ListRolesCommand({
                PathPrefix: '/aws-service-role/opensearchservice.amazonaws.com/',
            }),
        );

        // Only if the role for OpenSearch Service doesn't exist, it will be created.
        if (response.Roles?.length === 0) {
            new CfnServiceLinkedRole(this, 'OpensearchServiceLinkedRole', {
                awsServiceName: 'opensearchservice.amazonaws.com',
            });
        }
    }
}
