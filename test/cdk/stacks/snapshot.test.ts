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

import { Template } from 'aws-cdk-lib/assertions';
import { Stack } from 'aws-cdk-lib';
import MockApp from '../mocks/MockApp';
import fs from 'fs';
import path from 'path';

const BASELINE_DIR = path.join(__dirname, '__baselines__');
const UPDATE_BASELINES = process.argv.includes('--updateBaselines');

/**
 * Map of CloudFormation resource types to their immutable properties that cause replacement when changed.
 * This is not exhaustive but covers the most common resources and their replacement-triggering properties.
 */
const REPLACEMENT_PROPERTIES: Record<string, string[]> = {
    'AWS::S3::Bucket': ['BucketName'],
    'AWS::DynamoDB::Table': ['TableName', 'KeySchema', 'LocalSecondaryIndexes'],
    'AWS::Lambda::Function': ['FunctionName', 'Runtime'],
    'AWS::Lambda::LayerVersion': ['LayerName', 'CompatibleRuntimes'],
    'AWS::IAM::Role': ['RoleName', 'Path'],
    'AWS::IAM::Policy': ['PolicyName'],
    'AWS::IAM::ManagedPolicy': ['ManagedPolicyName', 'Path'],
    'AWS::SSM::Parameter': ['Name', 'Type'],
    'AWS::SQS::Queue': ['QueueName', 'FifoQueue'],
    'AWS::SNS::Topic': ['TopicName', 'FifoTopic'],
    'AWS::EC2::SecurityGroup': ['GroupName', 'VpcId'],
    'AWS::EC2::VPC': ['CidrBlock'],
    'AWS::EC2::Subnet': ['VpcId', 'AvailabilityZone', 'CidrBlock'],
    'AWS::ECS::Cluster': ['ClusterName'],
    'AWS::ECS::Service': ['ServiceName', 'LaunchType'],
    'AWS::ECS::TaskDefinition': ['Family'],
    'AWS::ElasticLoadBalancingV2::LoadBalancer': ['Name', 'Scheme', 'Type'],
    'AWS::ElasticLoadBalancingV2::TargetGroup': ['TargetType', 'Protocol', 'Port', 'VpcId'],
    'AWS::ApiGateway::RestApi': ['Name'],
    'AWS::ApiGateway::Resource': ['ParentId', 'PathPart', 'RestApiId'],
    'AWS::ApiGateway::Method': ['HttpMethod', 'ResourceId', 'RestApiId'],
    'AWS::CloudWatch::Alarm': ['AlarmName'],
    'AWS::Logs::LogGroup': ['LogGroupName'],
    'AWS::KMS::Key': ['KeySpec', 'KeyUsage'],
    'AWS::KMS::Alias': ['AliasName'],
    'AWS::SecretsManager::Secret': ['Name'],
    'AWS::RDS::DBInstance': ['DBInstanceIdentifier', 'Engine', 'DBName'],
    'AWS::RDS::DBCluster': ['DBClusterIdentifier', 'Engine', 'DatabaseName'],
    'AWS::Cognito::UserPool': ['UserPoolName'],
    'AWS::Cognito::UserPoolClient': ['ClientName'],
    'AWS::StepFunctions::StateMachine': ['StateMachineName', 'StateMachineType'],
    'AWS::Events::Rule': ['Name', 'EventBusName'],
    'AWS::CloudFront::Distribution': [],
    'AWS::Route53::HostedZone': ['Name'],
    'AWS::ECR::Repository': ['RepositoryName'],
    'AWS::OpenSearchService::Domain': ['DomainName'],
    'AWS::Elasticsearch::Domain': ['DomainName'],
};

interface BreakingChange {
    type: 'REMOVED' | 'TYPE_CHANGED' | 'REPLACEMENT_PROPERTY' | 'STATEFUL_REMOVED';
    logicalId: string;
    resourceType: string;
    details: string;
    severity: 'HIGH' | 'MEDIUM' | 'LOW';
}

/**
 * Resource types that are stateful and their removal would cause data loss.
 */
const STATEFUL_RESOURCES = new Set([
    'AWS::S3::Bucket',
    'AWS::DynamoDB::Table',
    'AWS::RDS::DBInstance',
    'AWS::RDS::DBCluster',
    'AWS::EFS::FileSystem',
    'AWS::OpenSearchService::Domain',
    'AWS::Elasticsearch::Domain',
    'AWS::Cognito::UserPool',
    'AWS::SecretsManager::Secret',
    'AWS::SSM::Parameter',
    'AWS::KMS::Key',
]);

describe('Stack Migration Tests', () => {
    const stacks = MockApp.getStacks();

    stacks?.forEach((stack: Stack) => {
        it(`${stack.stackName} has no breaking changes`, () => {
            const template = Template.fromStack(stack);
            const current = template.toJSON();
            const baselinePath = path.join(BASELINE_DIR, `${stack.stackName}.json`);

            if (!fs.existsSync(baselinePath)) {
                console.warn(`No baseline found for ${stack.stackName}, creating one`);
                fs.mkdirSync(BASELINE_DIR, { recursive: true });
                fs.writeFileSync(baselinePath, JSON.stringify(current, null, 2));
                return;
            }

            const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
            const breakingChanges = detectBreakingChanges(baseline, current);

            if (breakingChanges.length > 0) {
                if (UPDATE_BASELINES) {
                    console.warn(`\n⚠️  Updating baseline for ${stack.stackName} due to breaking changes:`);
                    breakingChanges.forEach((change) => {
                        const severityIcon = change.severity === 'HIGH' ? '🔴' : change.severity === 'MEDIUM' ? '🟡' : '🟢';
                        console.warn(`  ${severityIcon} [${change.type}] ${change.logicalId} (${change.resourceType})`);
                        console.warn(`     ${change.details}`);
                    });
                    fs.writeFileSync(baselinePath, JSON.stringify(current, null, 2));
                    return;
                }

                console.error(`\n❌ Breaking changes detected in ${stack.stackName}:`);
                breakingChanges.forEach((change) => {
                    const severityIcon = change.severity === 'HIGH' ? '🔴' : change.severity === 'MEDIUM' ? '🟡' : '🟢';
                    console.error(`  ${severityIcon} [${change.type}] ${change.logicalId} (${change.resourceType})`);
                    console.error(`     ${change.details}`);
                });
                console.error('\nTo update baselines after intentional changes, run:');
                console.error(`  npm run test:update-baselines\n`);
            }

            expect(breakingChanges).toEqual([]);
        });
    });
});

/**
 * Detects breaking changes between baseline and current CloudFormation templates.
 * Breaking changes include:
 * - Removed resources (logical ID exists in baseline but not in current)
 * - Type changes (same logical ID but different resource type)
 * - Immutable property changes that trigger resource replacement
 */
function detectBreakingChanges(baseline: any, current: any): BreakingChange[] {
    const breakingChanges: BreakingChange[] = [];
    const baselineResources = baseline.Resources || {};
    const currentResources = current.Resources || {};

    // Check for removed resources
    for (const [logicalId, baselineResource] of Object.entries(baselineResources)) {
        const resource = baselineResource as { Type: string; Properties?: Record<string, unknown> };
        const currentResource = currentResources[logicalId] as { Type: string; Properties?: Record<string, unknown> } | undefined;

        if (!currentResource) {
            const isStateful = STATEFUL_RESOURCES.has(resource.Type);
            breakingChanges.push({
                type: isStateful ? 'STATEFUL_REMOVED' : 'REMOVED',
                logicalId,
                resourceType: resource.Type,
                details: isStateful
                    ? `Stateful resource removed - this will cause DATA LOSS`
                    : `Resource removed - CloudFormation will delete this resource`,
                severity: isStateful ? 'HIGH' : 'MEDIUM',
            });
            continue;
        }

        // Check for type changes
        if (resource.Type !== currentResource.Type) {
            breakingChanges.push({
                type: 'TYPE_CHANGED',
                logicalId,
                resourceType: resource.Type,
                details: `Type changed from ${resource.Type} to ${currentResource.Type}`,
                severity: 'HIGH',
            });
            continue;
        }

        // Check for replacement-triggering property changes
        const replacementProps = REPLACEMENT_PROPERTIES[resource.Type] || [];
        for (const prop of replacementProps) {
            const baselineValue = resource.Properties?.[prop];
            const currentValue = currentResource.Properties?.[prop];

            if (baselineValue !== undefined && !deepEqual(baselineValue, currentValue)) {
                breakingChanges.push({
                    type: 'REPLACEMENT_PROPERTY',
                    logicalId,
                    resourceType: resource.Type,
                    details: `Property '${prop}' changed from ${JSON.stringify(baselineValue)} to ${JSON.stringify(currentValue)} - this triggers REPLACEMENT`,
                    severity: STATEFUL_RESOURCES.has(resource.Type) ? 'HIGH' : 'MEDIUM',
                });
            }
        }
    }

    return breakingChanges;
}

/**
 * Deep equality check for CloudFormation property values.
 * Handles objects, arrays, and primitive values.
 */
function deepEqual(a: unknown, b: unknown): boolean {
    if (a === b) return true;
    if (a === null || b === null) return false;
    if (typeof a !== typeof b) return false;

    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return false;
        return a.every((val, idx) => deepEqual(val, b[idx]));
    }

    if (typeof a === 'object' && typeof b === 'object') {
        const aObj = a as Record<string, unknown>;
        const bObj = b as Record<string, unknown>;
        const aKeys = Object.keys(aObj);
        const bKeys = Object.keys(bObj);

        if (aKeys.length !== bKeys.length) return false;
        return aKeys.every((key) => deepEqual(aObj[key], bObj[key]));
    }

    return false;
}
