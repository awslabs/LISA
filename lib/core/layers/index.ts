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

import { BundlingOutput } from 'aws-cdk-lib';
import { Architecture, Code, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Asset } from 'aws-cdk-lib/aws-s3-assets';
import { Construct } from 'constructs';

import { BaseProps } from '../../schema';

/**
 * Properties for Layer Construct.
 * @property {string} path - The path to the directory containing relevant files.
 * @property {string} description - The Description of the LayerVersion.
 * @property {Architecture} architecture - Lambda runtime architecture.
 * @property {boolean} autoUpgrade - Whether to upgrade libraries during the pip install.
 * @property {boolean} slimDeployment - Remove extra files to slim down deployment.
 * @property {boolean} removePackages - Specific packages to remove from deployment.
 */
type LayerProps = {
    path: string;
    description: string;
    architecture: Architecture;
    autoUpgrade?: boolean;
    slimDeployment?: boolean;
    removePackages?: string[];
    assetPath?: string;
} & BaseProps;

/**
 * Create a Lambda layer.
 */
export class Layer extends Construct {
    /** The Lambda LayerVersion to use across Lambda functions. */
    public layer: LayerVersion;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LayerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: LayerProps) {
        super(scope, id);

        const { assetPath, config, path, description, architecture, autoUpgrade, slimDeployment, removePackages } = props;

        let layerCode: Code;
        if (assetPath) {
            layerCode = Code.fromAsset(assetPath);
        } else {
            const outputDirectory = '/asset-output/python';
            const args = [`mkdir -p ${outputDirectory} && cp -R . ${outputDirectory}`];
            args.push(`&& pip install -r requirements.txt -t ${outputDirectory}`);
            if (config.region.includes('iso')) {
                args.push(`-i ${config.pypiConfig.indexUrl} --trusted-host ${config.pypiConfig.trustedHost}`);
            }
            if (autoUpgrade) {
                args.push('--upgrade');
            }
            if (slimDeployment) {
                args.push(`&& find ${outputDirectory} -name "*__pycache__*" -type d -exec rm -r {} +`);
                // Be careful here, some libraries will fail if we use the + sign so we iterate one by one instead
                args.push(`&& find ${outputDirectory} -name "test*" -type d -exec rm -r {} \\; || true`);
            }
            if (removePackages) {
                for (const pkg of removePackages) {
                    args.push(`&& rm -rf ${outputDirectory}/${pkg}`);
                }
            }

            const layerAsset = new Asset(this, 'LayerAsset', {
                path,
                bundling: {
                    image: Runtime.PYTHON_3_11.bundlingImage,
                    platform: architecture.dockerPlatform,
                    command: ['bash', '-c', `set -e ${args.join(' ')}`],
                    outputType: BundlingOutput.AUTO_DISCOVER,
                    securityOpt: 'no-new-privileges:true',
                    network: 'host',
                },
            });
            layerCode = Code.fromBucket(layerAsset.bucket, layerAsset.s3ObjectKey);
        }

        const layer = new LayerVersion(this, 'Layer', {
            code: layerCode,
            compatibleRuntimes: [Runtime.PYTHON_3_11],
            removalPolicy: config.removalPolicy,
            description: description,
        });

        this.layer = layer;
    }
}
