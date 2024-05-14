// LISA-serve Stack.
import { Stack, StackProps } from 'aws-cdk-lib';
import { ManagedPolicy, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { createCdkId, getIamPolicyStatements, getModelIdentifier } from './core/utils';
import { BaseProps } from './schema';

/**
 * Properties for the LisaServeIAMStack Construct.
 */
interface LisaIAMStackProps extends BaseProps, StackProps {}

/**
 * Properties for the Task Role Information interface.
 * @param {string} modelName - Model name for Task.
 * @param {iam.Role} role - IAM Role Model Task.
 */
interface RoleInfo {
  modelName: string;
  roleName: string;
  roleArn: string;
}

enum ECSTaskType {
  API = 'API',
  MODEL = 'model endpoint',
}

/**
 * LisaServe IAM stack.
 */
export class LisaServeIAMStack extends Stack {
  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaIAMStackProps} props - Properties for the Stack.
   */
  public readonly taskRoles: RoleInfo[] = [];
  public readonly autoScalingGroupIamRole: Role;

  constructor(scope: Construct, id: string, props: LisaIAMStackProps) {
    super(scope, id, props);
    const { config } = props;
    // Add suppression for IAM4 (use of managed policy)
    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'Allow use of AmazonSSMManagedInstanceCore policy to allow EC2 to enable SSM core functionality.',
      },
    ]);

    // role for auto scaling group for ECS cluster
    this.autoScalingGroupIamRole = new Role(this, createCdkId([config.deploymentName, 'ASGRole']), {
      roleName: createCdkId([config.deploymentName, 'ASGRole']),
      assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
    });
    this.autoScalingGroupIamRole.addManagedPolicy(
      ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
    );

    /**
     * Create role for Lambda execution if deploying RAG
     */
    if (config.deployRag) {
      const lambdaPolicyStatements = getIamPolicyStatements(config, 'rag');
      const lambdaRagPolicy = new ManagedPolicy(this, createCdkId([config.deploymentName, 'RAGPolicy']), {
        managedPolicyName: createCdkId([config.deploymentName, 'RAGPolicy']),
        statements: lambdaPolicyStatements,
      });
      const ragLambdaRoleName = createCdkId([config.deploymentName, 'RAGRole']);
      const ragLambdaRole = new Role(this, 'LisaRagLambdaExecutionRole', {
        assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
        roleName: ragLambdaRoleName,
        description: 'Role used by RAG API lambdas to access AWS resources',
        managedPolicies: [lambdaRagPolicy],
      });
      new StringParameter(this, createCdkId(['LisaRagRole', 'StringParameter']), {
        parameterName: `${config.deploymentPrefix}/roles/${ragLambdaRoleName}`,
        stringValue: ragLambdaRole.roleArn,
        description: `Role ARN for LISA ${ragLambdaRoleName}`,
      });
    }

    /**
     * Create roles for ECS tasks. Currently all deployed models and all API ECS tasks use
     * an identical role. In the future it's possible the models and API containers may need
     * specific roles
     */
    const statements = getIamPolicyStatements(config, 'ecs');
    const taskPolicy = new ManagedPolicy(this, createCdkId([config.deploymentName, 'ECSPolicy']), {
      managedPolicyName: createCdkId([config.deploymentName, 'ECSPolicy']),
      statements,
    });
    const ecsRoles = [
      {
        id: 'REST',
        type: ECSTaskType.API,
      },
    ];
    for (const modelConfig of config.ecsModels) {
      if (modelConfig.deploy) {
        ecsRoles.push({
          id: getModelIdentifier(modelConfig),
          type: ECSTaskType.MODEL,
        });
      }
    }
    ecsRoles.forEach((role) => {
      const roleName = createCdkId([config.deploymentName, role.id, 'Role']);
      const taskRole = new Role(this, createCdkId([role.id, 'Role']), {
        assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
        roleName,
        description: `Allow ${role.id} ${role.type} ECS task access to AWS resources`,
        managedPolicies: [taskPolicy],
      });
      new StringParameter(this, createCdkId([config.deploymentName, role.id, 'SP']), {
        parameterName: `${config.deploymentPrefix}/roles/${role.id}`,
        stringValue: taskRole.roleArn,
        description: `Role ARN for LISA ${role.type} ${role.id} ECS Task`,
      });
    });
  }
}
