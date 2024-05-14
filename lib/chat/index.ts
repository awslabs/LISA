// LisaChat Stack.
import { Stack, StackProps } from 'aws-cdk-lib';
import { IAuthorizer } from 'aws-cdk-lib/aws-apigateway';
import { ISecurityGroup, IVpc } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

import { SessionApi } from './api/session';
import { BaseProps } from '../schema';

interface CustomLisaChatStackProps extends BaseProps {
  authorizer: IAuthorizer;
  restApiId: string;
  rootResourceId: string;
  securityGroups?: ISecurityGroup[];
  vpc?: IVpc;
}
type LisaChatStackProps = CustomLisaChatStackProps & StackProps;

/**
 * LisaChat Application stack.
 */
export class LisaChatApplicationStack extends Stack {
  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaChatStackProps} props - Properties for the Stack.
   */
  constructor(scope: Construct, id: string, props: LisaChatStackProps) {
    super(scope, id, props);

    const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

    // Add REST API Lambdas to APIGW
    new SessionApi(this, 'SessionApi', {
      authorizer,
      config,
      restApiId,
      rootResourceId,
      securityGroups,
      vpc,
    });
  }
}
