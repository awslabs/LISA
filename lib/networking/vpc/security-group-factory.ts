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

import { ISecurityGroup, ISubnet, IVpc, Peer, Port, SecurityGroup } from 'aws-cdk-lib/aws-ec2';
import { createCdkId } from '../../core/utils';
import { SecurityGroupNames } from '../../core/iam/SecurityGroups';
import { IConstruct } from 'constructs';
import { Config } from '../../schema';
import { Vpc } from '.';

/**
 * Security Group Factory to create consistent security groups
 */
export class SecurityGroupFactory {

    /**
     * Creates a security group for the VPC.
     *
     * @param construct - Construct for security group
     * @param securityGroupOverride - security group override
     * @param {string} securityGroupId - The name of the security group.
     * @param {string} deploymentName - The deployment name.
     * @param {Vpc} vpc - The virtual private cloud.
     * @param {string} description - The description of the security group.
     * @returns {ISecurityGroup} The security group.
     */
    static createSecurityGroup (
        construct: IConstruct,
        securityGroupOverride: string | undefined,
        securityGroupId: string,
        deploymentName: string | undefined,
        vpc: IVpc,
        description: string,
    ): ISecurityGroup {
        if (securityGroupOverride) {
            console.debug(`Security Role Override provided. Using ${securityGroupOverride} for ${securityGroupId}`);
            const sg = SecurityGroup.fromSecurityGroupId(construct, securityGroupId, securityGroupOverride);
            // Validate the security group exists
            if (!sg) {
                throw new Error(`Security group ${sg} not found`);
            }
            return sg;
        } else {
            const securityGroupName = SecurityGroupNames[securityGroupId];
            return new SecurityGroup(construct, securityGroupId, {
                vpc: vpc,
                description: `Security group for ${description}`,
                ...(securityGroupName && { securityGroupName: createCdkId(deploymentName ? [deploymentName, securityGroupName] : [securityGroupName]) }),
            });
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
    static addHttpsTraffic (securityGroup: ISecurityGroup): void {
        securityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443), 'Allow any traffic on port 443');
    }

    /**
      * Creates a security group for the VPC.
      *
      * @param {ISecurityGroup} securityGroup - The security Group.
      * @param {string} securityGroupName - The security Group name.
      * @param {Vpc} vpc - The virtual private cloud.
      * @param {number} port - port for ingress
      * @param {ISubnet[]} subnets - subnets if using predefined vpc
      */
    static addIngress (
        securityGroup: ISecurityGroup,
        securityGroupName: string,
        vpc: IVpc,
        port: number,
        subnets?: ISubnet[]): void {
        const subNets = subnets || vpc.isolatedSubnets.concat(vpc.privateSubnets);
        subNets?.forEach((subnet) => {
            securityGroup.connections.allowFrom(
                Peer.ipv4(subnets ? subNets.filter((filteredSubnet: { subnetId: string; }) =>
                    filteredSubnet.subnetId === subnet.subnetId)?.[0]?.ipv4CidrBlock : subnet.ipv4CidrBlock),
                Port.tcp(port),
                `Allow REST API private subnets to communicate with ${securityGroupName}`,
            );
        });
    }

    /**
     * Creates a security group for the VPC.
     *
     * @param {ISecurityGroup} securityGroup - The security Group.
     * @param {string} securityGroupName - The security Group name.
     * @param {Vpc} vpc - The virtual private cloud.
     * @param {Config} config - LISA config.
     */
    static legacyAddIngress (
        securityGroup: ISecurityGroup,
        securityGroupName: string,
        vpc: Vpc,
        config: Config,
        port: number): void {
        const subNets = config.subnets && config.vpcId ? vpc.subnetSelection?.subnets : vpc.vpc.isolatedSubnets.concat(vpc.vpc.privateSubnets);
        subNets?.forEach((subnet) => {
            securityGroup.connections.allowFrom(
                Peer.ipv4((config.subnets && Array.isArray(config.subnets) ) ? config.subnets.filter((filteredSubnet: { subnetId: string; }) =>
                    filteredSubnet.subnetId === subnet.subnetId)?.[0]?.ipv4CidrBlock :  subnet.ipv4CidrBlock),
                Port.tcp(port),
                `Allow REST API private subnets to communicate with ${securityGroupName}`,
            );
        });
    }
}
