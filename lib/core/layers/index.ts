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

import { Architecture, Code, LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { BaseProps } from '../../schema';
import { getDefaultRuntime } from '../../api-base/utils';
import * as path from 'node:path';
import * as fs from 'node:fs';
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
    afterBundle?: (inputDir: string, outputDir: string) => string[];
} & BaseProps;

/**
 * Create a Lambda layer.
 */
export class Layer extends Construct {
    /** The Lambda LayerVersion to use across Lambda functions. */
    public layer!: LayerVersion;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {LayerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: LayerProps) {
        super(scope, id);

        const { assetPath, config, path: layerPath, description, architecture, afterBundle } = props;

        if (!fs.existsSync(`${layerPath}/requirements.txt`)) {
            throw new Error(`requirements.txt not found in ${layerPath}`);
        }
        const packagesExists = fs.existsSync(path.join(layerPath, 'packages'));

        try {
            if (assetPath) {
                this.layer = new LayerVersion(this, 'Layer', {
                    code: Code.fromAsset(assetPath),
                    description,
                    compatibleRuntimes: [getDefaultRuntime()],
                    removalPolicy: config.removalPolicy,
                });
            } else {
                console.error(`Building layer: ${id} path:${layerPath}`);
                // Use PythonLayerVersion with bundling as before
                this.layer = new PythonLayerVersion(this, 'Layer', {
                    entry: layerPath,
                    description,
                    compatibleRuntimes: [getDefaultRuntime()],
                    removalPolicy: config.removalPolicy,
                    bundling: {
                        platform: architecture.dockerPlatform,
                        commandHooks: (packagesExists || afterBundle) ? {
                            beforeBundling (inputDir: string, outputDir: string): string[] {
                                return [`touch ${outputDir}/requirements.txt`];
                            },
                            afterBundling (inputDir: string, outputDir: string): string[] {
                                const commands = [];
                                if (packagesExists) {
                                    commands.push(`cp -r ${inputDir}/packages/* ${outputDir}/python/`);
                                }
                                if (afterBundle) {
                                    commands.push(...afterBundle(inputDir, outputDir));
                                }
                                return commands;
                            },
                        } : undefined
                    },
                });
            }
        } catch (error) {
            console.error('Layer bundling failed:', error);
            console.error('Asset path:', layerPath);
            console.error('Current working directory:', process.cwd());
            throw error;
        }
    }
}
