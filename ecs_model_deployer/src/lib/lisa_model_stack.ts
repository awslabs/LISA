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

import { Aspects, CfnResource, IAspect, Stack, StackProps } from 'aws-cdk-lib';

import { SecurityGroup, Subnet, SubnetSelection, Vpc } from 'aws-cdk-lib/aws-ec2';

import { Construct } from 'constructs';
import { EcsModel } from './ecs-model';

import { Config,EcsClusterConfig } from '#root/lib/schema';

export type LisaModelStackProps = {
    vpcId: string;
    securityGroupId: string;
    config: Config;
    modelConfig: EcsClusterConfig;
} & StackProps;

/**
 * Modifies all AWS::EC2::LaunchTemplate resources in a CDK application. It directly adjusts the synthesized
 * CloudFormation template, setting the HttpPutResponseHopLimit within MetadataOptions to 2 and HttpTokens to required.
 */
class UpdateLaunchTemplateMetadataOptions implements IAspect {
    /**
   * Checks if the given node is an instance of CfnResource and specifically an AWS::EC2::LaunchTemplate resource.
   * If both conditions are true, it applies a direct override to the CloudFormation resource's properties, setting
   * the HttpPutResponseHopLimit to 2 and HttpTokens to 'required'.
   *
   * @param {Construct} node - The CDK construct being visited.
   */
    public visit (node: Construct): void {
    // Check if the node is a CloudFormation resource of type AWS::EC2::LaunchTemplate
        if (node instanceof CfnResource && node.cfnResourceType === 'AWS::EC2::LaunchTemplate') {
            // Directly modify the CloudFormation properties to include the desired settings
            node.addOverride('Properties.LaunchTemplateData.MetadataOptions.HttpPutResponseHopLimit', 2);
            node.addOverride('Properties.LaunchTemplateData.MetadataOptions.HttpTokens', 'required');
        }
    }
}

export class LisaModelStack extends Stack {
    constructor (scope: Construct, id: string, props: LisaModelStackProps) {
        super(scope, id, props);

        const vpc = Vpc.fromLookup(this, `${id}-vpc`, {
            vpcId: props.vpcId
        });

        let subnetSelection: SubnetSelection | undefined;

        if (props.config.subnets && props.config.subnets.length > 0) {
            subnetSelection = {
                subnets: props.config.subnets?.map((subnet, index) => Subnet.fromSubnetId(this, index.toString(), subnet.subnetId))
            };
        }

        const securityGroup = SecurityGroup.fromLookupById(this, `${id}-sg`, props.securityGroupId);

        new EcsModel(this, `${id}-ecsModel`, {
            config: props.config,
            modelConfig: props.modelConfig,
            securityGroup: securityGroup,
            vpc: vpc,
            subnetSelection: subnetSelection
        });

        Aspects.of(this).add(new UpdateLaunchTemplateMetadataOptions());
    }
}
