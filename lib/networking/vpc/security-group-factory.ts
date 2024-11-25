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

import { ISecurityGroup, IVpc, Peer, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { Config } from '../../schema';
import { createCdkId } from '../../core/utils';
import { Vpc } from '.';
import { IConstruct } from 'constructs';

/**
 * Security Group Factory to create consistent security groups
 */
export class SecurityGroupFactory {

    /**
     * Creates a security group for the VPC.
     *
     * @param securityGroupOverride - security group override
     * @param {string} securityGroupName - The name of the security group.
     * @param {string} deploymentName - The deployment name.
     * @param {Vpc} vpc - The virtual private cloud.
     * @param {string} description - The description of the security group.
     * @returns {ISecurityGroup} The security group.
     */
    static createSecurityGroup (
        construct: IConstruct,
        securityGroupOverride: string | undefined,
        securityGroupName: string,
        deploymentName: string,
        vpc: IVpc,
        description: string,
    ): ISecurityGroup {
        if (securityGroupOverride) {
            console.log(`Security Role Override provided. Using ${securityGroupOverride} for ${securityGroupName}`);
            const sg = SecurityGroup.fromSecurityGroupId(construct, securityGroupName, securityGroupOverride);
            // Validate the security group exists
            if (!sg) {
                throw new Error(`Security group ${sg} not found`);
            }
            return sg;
        } else {
            const sg = new SecurityGroup(construct, securityGroupName, {
                securityGroupName: createCdkId([deploymentName, securityGroupName]),
                vpc: vpc,
                description: `Security group for ${description}`,
            });

            return sg;
        }
    }

    /**
     * Add VPC traffic to the security group.
     * @param securityGroup
     * @param vpcCidrBlock
     */
    static addVpcTraffic (securityGroup: ISecurityGroup, vpcCidrBlock: string): void {
        securityGroup.addIngressRule(Peer.ipv4(vpcCidrBlock), Port.tcp(80), 'Allow VPC traffic on port 80');
    }

    /**
     * Add HTTPS traffic to the security group.
     * @param securityGroup
     */
    static addHttpsTraffic (securityGroup: ISecurityGroup ): void {
        securityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443), 'Allow any traffic on port 443');
    }

    /**
     * Creates a security group for the VPC.
     *
     * @param {ISecurityGroup} securityGroup - The security Group.
     * @param {string} securityGroupName - The security Group name.
     * @param {Vpc} vpc - The virtual private cloud.
     * @param {Config} config - LISA config.
     */
    static addIngress (
        securityGroup: ISecurityGroup,
        securityGroupName: string,
        vpc: Vpc,
        config: Config): void {
        const subNets = config.subnets && config.vpcId ? vpc.subnetSelection?.subnets : vpc.vpc.isolatedSubnets.concat(vpc.vpc.privateSubnets);
        subNets?.forEach((subnet) => {
            securityGroup.connections.allowFrom(
                Peer.ipv4(config.subnets ? config.subnets.filter((filteredSubnet: { subnetId: string; }) =>
                    filteredSubnet.subnetId === subnet.subnetId)?.[0]?.ipv4CidrBlock :  subnet.ipv4CidrBlock),
                Port.tcp(config.restApiConfig.rdsConfig.dbPort),
                `Allow REST API private subnets to communicate with ${securityGroupName}`,
            );
        });
    }
}