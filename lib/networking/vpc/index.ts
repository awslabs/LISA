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

// VPC Construct.
import { CfnOutput } from 'aws-cdk-lib';
import {
    GatewayVpcEndpointAwsService,
    IpAddresses,
    ISecurityGroup,
    IVpc,
    NatProvider,
    Peer,
    Port,
    SecurityGroup,
    Subnet,
    SubnetSelection,
    SubnetType,
    Vpc as ec2Vpc,
} from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { createCdkId } from '../../core/utils';
import { BaseProps, SecurityGroups } from '../../schema';
import { SecurityGroups as SecurityGroupsEnum } from '../../core/iam/SecurityGroups';
import { SubnetGroup } from 'aws-cdk-lib/aws-rds';

type VpcProps = {} & BaseProps;

/**
 * Creates a virtual private cloud (VPC) and other networking resources.
 */
export class Vpc extends Construct {
    /** Virtual private cloud. */
    public readonly vpc: IVpc;

    /** Security groups for application. */
    public readonly securityGroups: SecurityGroups;

    /** Created from deployment configured Subnets for application. */
    public readonly subnetGroup?: SubnetGroup;

    /** Imported Subnets for application. */
    public readonly subnetSelection?: SubnetSelection;

    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param props
     */
    constructor (scope: Construct, id: string, props: VpcProps) {
        super(scope, id);
        const { config } = props;

        let vpc: IVpc;
        if (config.vpcId) {
            // Imports VPC for use by application if supplied, else creates a VPC.
            vpc = ec2Vpc.fromLookup(this, 'imported-vpc', {
                vpcId: config.vpcId,
            });

            // Checks if SubnetIds are provided in the config, if so we import them for use.
            // A VPC must be supplied if Subnets are being used.
            if (config.subnets && config.subnets.length > 0) {
                this.subnetSelection = {
                    subnets: props.config.subnets?.map((subnet, index) => Subnet.fromSubnetId(this, index.toString(), subnet.subnetId))
                };

                this.subnetGroup = new SubnetGroup(this, createCdkId([config.deploymentName, 'Imported-Subnets']), {
                    vpc: vpc,
                    description: 'This SubnetGroup is made up of imported Subnets via the deployment config',
                    vpcSubnets: this.subnetSelection,
                });
            }
        } else {
            // Create VPC
            vpc = new ec2Vpc(this, 'VPC', {
                vpcName: 'LISA-VPC',
                maxAzs: 2,
                ipAddresses: IpAddresses.cidr('10.0.0.0/22'),
                natGatewayProvider: NatProvider.gateway(),
                natGateways: 1,
                subnetConfiguration: [
                    {
                        subnetType: SubnetType.PUBLIC,
                        name: 'public',
                        cidrMask: 26,
                    },
                    {
                        subnetType: SubnetType.PRIVATE_ISOLATED,
                        name: 'privateIsolated',
                        cidrMask: 26,
                    },
                    {
                        subnetType: SubnetType.PRIVATE_WITH_EGRESS,
                        name: 'private',
                        cidrMask: 26,
                    },
                ],
            });

            // VPC endpoint for S3
            vpc.addGatewayEndpoint('S3GatewayEndpoint', {
                service: GatewayVpcEndpointAwsService.S3,
            });

            // VPC endpoint for DynamoDB
            if (!config.region.includes('iso')) {
                vpc.addGatewayEndpoint('DynamoDBEndpoint', {
                    service: GatewayVpcEndpointAwsService.DYNAMODB,
                });
            }
        }

        const sgOverrides = config.securityGroups;
        // Create security groups
        const ecsModelAlbSg = this.createSecurityGroup(
            sgOverrides,
            SecurityGroupsEnum.ECS_MODEL_ALB_SG,
            config.deploymentName,
            vpc,
            'ECS model application load balancer',
            true,
        );
        const restApiAlbSg = this.createSecurityGroup(
            sgOverrides,
            SecurityGroupsEnum.REST_API_ALB_SG,
            config.deploymentName,
            vpc,
            'REST API application load balancer',
            !!config.restApiConfig?.sslCertIamArn,
            !config.restApiConfig?.sslCertIamArn,
        );
        const lambdaSecurityGroup = this.createSecurityGroup(
            sgOverrides,
            SecurityGroupsEnum.LAMBDA_SG,
            config.deploymentName,
            vpc,
            'authorizer and API Lambdas',
        );

        // Update
        this.vpc = vpc;
        this.securityGroups = {
            ecsModelAlbSg: ecsModelAlbSg,
            restApiAlbSg: restApiAlbSg,
            lambdaSecurityGroup: lambdaSecurityGroup,
        };

        new CfnOutput(this, 'vpcArn', { value: vpc.vpcArn });
        new CfnOutput(this, 'vpcCidrBlock', { value: vpc.vpcCidrBlock });

        new CfnOutput(this, 'ecsModelAlbSg', { value: ecsModelAlbSg.securityGroupId });
        new CfnOutput(this, 'restApiAlbSg', { value: restApiAlbSg.securityGroupId });
        new CfnOutput(this, 'lambdaSecurityGroup', { value: lambdaSecurityGroup.securityGroupId });
    }

    /**
     * Creates a security group for the VPC.
     *
     * @param groupsConfig - security group overrides
     * @param {string} securityGroupId - The unique identifier for the security group.
     * @param {string} securityGroupName - The name of the security group.
     * @param {string} deploymentName - The deployment name.
     * @param {IVpc} vpc - The virtual private cloud.
     * @param {string} description - The description of the security group.
     * @param {boolean} allowVpcTraffic - Whether to allow VPC traffic.
     * @param {boolean} allowHttpsTraffic - Whether to allow HTTPS traffic.
     * @returns {ISecurityGroup} The security group.
     */
    createSecurityGroup (
        groupsConfig: Record<string, string> | undefined,
        securityGroupName: string,
        deploymentName: string,
        vpc: IVpc,
        description: string,
        allowVpcTraffic: boolean = false,
        allowHttpsTraffic: boolean = false,
    ): ISecurityGroup {
        if (groupsConfig?.[securityGroupName]) {
            return SecurityGroup.fromSecurityGroupId(this, securityGroupName, groupsConfig[securityGroupName]);
        } else {
            const sg = new SecurityGroup(this, securityGroupName, {
                securityGroupName: createCdkId([deploymentName, securityGroupName]),
                vpc: vpc,
                description: `Security group for ${description}`,
            });
            if (allowVpcTraffic) {
                sg.addIngressRule(Peer.ipv4(vpc.vpcCidrBlock), Port.tcp(80), 'Allow VPC traffic on port 80');
            }
            if (allowHttpsTraffic) {
                sg.addIngressRule(Peer.anyIpv4(), Port.tcp(443), 'Allow any traffic on port 443');
            }
            return sg;
        }
    }
}
