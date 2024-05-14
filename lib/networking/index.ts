import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { Vpc } from './vpc';
import { BaseProps } from '../schema';

/**
 * Lisa Networking stack.
 */
interface LisaNetworkingStackProps extends BaseProps, cdk.StackProps {}

/**
 * Lisa Networking stack. Defines a VPC for LISA
 */
export class LisaNetworkingStack extends cdk.Stack {
  /** Virtual private cloud. */
  public readonly vpc: Vpc;

  /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LisaNetworkingStackProps} props - Properties for the Stack.
   */
  constructor(scope: Construct, id: string, props: LisaNetworkingStackProps) {
    super(scope, id, props);

    const { config } = props;

    // Create VPC
    this.vpc = new Vpc(this, 'Vpc', {
      config: config,
    });
  }
}
