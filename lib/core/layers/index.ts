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

import { Architecture, Code, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { BaseProps } from '../../schema';
import { getPythonRuntime } from '../../api-base/utils';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { execSync } from 'node:child_process';
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
    /** Path to a requirements file whose packages should be installed with --no-deps. */
    noDepsRequirements?: string;
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

        const { assetPath, config, path: layerPath, description, architecture, afterBundle, noDepsRequirements } = props;

        if (!fs.existsSync(`${layerPath}/requirements.txt`)) {
            throw new Error(`requirements.txt not found in ${layerPath}`);
        }
        const packagesExists = fs.existsSync(path.join(layerPath, 'packages'));
        const hasNoDeps = noDepsRequirements && fs.existsSync(path.join(layerPath, noDepsRequirements));
        const useCommandHooks = packagesExists || afterBundle || hasNoDeps;

        try {
            if (assetPath) {
                this.layer = new LayerVersion(this, 'Layer', {
                    code: Code.fromAsset(assetPath),
                    description,
                    compatibleRuntimes: [getPythonRuntime()],
                    removalPolicy: config.removalPolicy,
                });
            } else {
                console.error(`Building layer: ${id} path:${layerPath}`);
                // Use PythonLayerVersion with bundling as before
                this.layer = new PythonLayerVersion(this, 'Layer', {
                    entry: layerPath,
                    description,
                    compatibleRuntimes: [getPythonRuntime()],
                    removalPolicy: config.removalPolicy,
                    bundling: {
                        platform: architecture.dockerPlatform,
                        commandHooks: useCommandHooks ? {
                            beforeBundling (inputDir: string, outputDir: string): string[] {
                                const commands = [`mkdir -p ${outputDir}/python && touch ${outputDir}/python/requirements.txt`];
                                if (hasNoDeps) {
                                    // Pre-install packages that need --no-deps before the normal pip install runs
                                    commands.push(
                                        `pip install --no-deps -r ${inputDir}/${noDepsRequirements} -t ${outputDir}/python`
                                    );
                                }
                                return commands;
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

/**
 * Properties for Node.js Layer Construct.
 */
type NodeLayerProps = {
    path: string;
    description: string;
    runtime: Runtime;
    assetPath?: string;
} & BaseProps;

/**
 * Create a Node.js Lambda layer.
 */
export class NodeLayer extends Construct {
    /** The Lambda LayerVersion to use across Lambda functions. */
    public layer!: LayerVersion;

    /**
   * @param {Construct} scope - The parent or owner of the construct.
   * @param {string} id - The unique identifier for the construct within its scope.
   * @param {NodeLayerProps} props - The properties of the construct.
   */
    constructor (scope: Construct, id: string, props: NodeLayerProps) {
        super(scope, id);

        const { assetPath, config, path: layerPath, description, runtime } = props;

        if (assetPath) {
            this.layer = new LayerVersion(this, 'Layer', {
                code: Code.fromAsset(assetPath),
                description,
                compatibleRuntimes: [runtime],
                removalPolicy: config.removalPolicy,
            });
        } else if (process.env.NODE_ENV === 'test') {
            // Skip npm install during tests - use mock layer directory
            const mockLayerDir = './test/cdk/mocks/layers';
            fs.mkdirSync(mockLayerDir, { recursive: true });
            this.layer = new LayerVersion(this, 'Layer', {
                code: Code.fromAsset(mockLayerDir),
                description,
                compatibleRuntimes: [runtime],
                removalPolicy: config.removalPolicy,
            });
        } else {
            // Build the layer locally
            const packageJsonPath = path.join(layerPath, 'package.json');
            if (!fs.existsSync(packageJsonPath)) {
                throw new Error(`package.json not found in ${layerPath}`);
            }

            // Create a temporary build directory
            const buildDir = path.join(layerPath, 'build');
            const nodejsDir = path.join(buildDir, 'nodejs');

            // Clean and create build directory
            if (fs.existsSync(buildDir)) {
                fs.rmSync(buildDir, { recursive: true, force: true });
            }
            fs.mkdirSync(nodejsDir, { recursive: true });

            // Copy package.json to build directory
            fs.copyFileSync(packageJsonPath, path.join(nodejsDir, 'package.json'));

            // Install dependencies
            console.log(`Building Node.js layer: ${id} at ${layerPath}`);
            execSync('npm install --omit=dev --production', {
                cwd: nodejsDir,
                stdio: 'inherit',
            });

            this.layer = new LayerVersion(this, 'Layer', {
                code: Code.fromAsset(buildDir),
                description,
                compatibleRuntimes: [runtime],
                removalPolicy: config.removalPolicy,
            });
        }
    }
}
