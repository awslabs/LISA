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
  Vpc as ec2Vpc,
  GatewayVpcEndpointAwsService,
  IpAddresses,
  IVpc,
  NatProvider,
  Peer,
  Port,
  SecurityGroup,
  SubnetType,
} from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { createCdkId } from '../../core/utils';
import { SecurityGroups, BaseProps } from '../../schema';

interface VpcProps extends BaseProps {}

/**
 * Creates a virtual private cloud (VPC) and other networking resources.
 */
export class Vpc extends Construct {
  /** Virtual private cloud. */
  public readonly vpc: IVpc;

  /** Security groups for application. */
  public readonly securityGroups: SecurityGroups;

  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   */
  constructor(scope: Construct, id: string, props: VpcProps) {
    super(scope, id);
    const { config } = props;

    let vpc: IVpc;
    if (config.vpcId) {
      vpc = ec2Vpc.fromLookup(this, 'imported-vpc', {
        vpcId: config.vpcId,
      });
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

    // Create security groups
    const ecsModelAlbSg = new SecurityGroup(this, 'EcsModelAlbSg', {
      securityGroupName: createCdkId([config.deploymentName, 'ECS-ALB-SG']),
      vpc: vpc,
      description: 'Security group for ECS model application load balancer',
    });
    const restApiAlbSg = new SecurityGroup(this, 'RestApiAlbSg', {
      securityGroupName: createCdkId([config.deploymentName, 'RestAPI-ALB-SG']),
      vpc: vpc,
      description: 'Security group for REST API application load balancer',
    });
    const lambdaSecurityGroup = new SecurityGroup(this, 'LambdaSecurityGroup', {
      securityGroupName: createCdkId([config.deploymentName, 'Lambda-SG']),
      vpc: vpc,
      description: 'Security group for authorizer and API Lambdas',
    });

    // Configure security group rules
    // All HTTP VPC traffic -> ECS model ALB
    ecsModelAlbSg.addIngressRule(Peer.ipv4(vpc.vpcCidrBlock), Port.tcp(80), 'Allow VPC traffic on port 80');

    // All HTTPS IPV4 traffic -> REST API ALB
    restApiAlbSg.addIngressRule(Peer.anyIpv4(), Port.tcp(443), 'Allow any traffic on port 443');

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
}
