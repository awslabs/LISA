import { Stack, StackProps } from 'aws-cdk-lib';
import { Deployment, RestApi } from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

import { BaseProps } from '../schema';

interface LisaApiDeploymentStackProps extends BaseProps, StackProps {
  restApiId: string;
}

export class LisaApiDeploymentStack extends Stack {
  constructor(scope: Construct, id: string, props: LisaApiDeploymentStackProps) {
    super(scope, id, props);

    const { restApiId, config } = props;

    // Workaround so that the APIGW endpoint always updates with the latest changes across all stacks
    // Relevant CDK issues:
    // https://github.com/aws/aws-cdk/issues/12417
    // https://github.com/aws/aws-cdk/issues/13383
    const deployment = new Deployment(this, `Deployment-${new Date().getTime()}`, {
      api: RestApi.fromRestApiId(this, 'restApiRef', restApiId),
    });

    // Hack to allow deploying to an existing stage
    // https://github.com/aws/aws-cdk/issues/25582
    (deployment as any).resource.stageName = config.deploymentStage;
  }
}
