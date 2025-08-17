#!/usr/bin/env node

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

// Main app
import * as fs from 'node:fs';
import * as path from 'node:path';

import * as cdk from 'aws-cdk-lib';
import * as yaml from 'js-yaml';
import _ from 'lodash';

import { Config, ConfigFile, ConfigSchema } from '../lib/schema';
import { LisaServeApplicationStage } from '../lib/stages';
import { SSMClient, GetParameterCommand, SSMServiceException } from '@aws-sdk/client-ssm';

async function readAndMergeConfigs(): Promise<any> {
    // Read configuration files
    const baseConfigFilePath = path.join(__dirname, '../config-base.yaml');
    const customConfigFilePath = path.join(__dirname, '../config-custom.yaml');
    const baseConfigFile = yaml.load(fs.readFileSync(baseConfigFilePath, 'utf8')) as ConfigFile;
    const customConfigFile = yaml.load(fs.readFileSync(customConfigFilePath, 'utf8')) as ConfigFile;
    const configData = _.merge(baseConfigFile, customConfigFile);

    // Other command line argument overrides
    type EnvMapping = [string, keyof Config];
    const mappings: EnvMapping[] = [
        ['PROFILE', 'profile'],
        ['DEPLOYMENT_NAME', 'deploymentName'],
        ['ACCOUNT_NUMBER', 'accountNumber'],
        ['PARTITION', 'partition'],
        ['DOMAIN', 'domain'],
        ['REGION', 'region'],
    ];
    mappings.forEach(([envVar, configVar]) => {
        const envValue = process.env[envVar];
        if (envValue) {
            (configData as any)[configVar] = envValue;
        }
    });

    return configData;
}

async function validateConfig(configData: any): Promise<Config> {
    try {
        // Validate and parse configuration
        const config = await ConfigSchema.parseAsync(configData);
        console.log('MERGED CONFIG FILE:\n' + yaml.dump(config));
        return config;
    } catch (error) {
        if (error instanceof Error) {
            console.error('Error parsing the configuration:', error.message);
        } else {
            console.error('An unexpected error occurred:', error);
        }
        process.exit(1);
    }
}

async function getExistingRagRepositories (config: Config): Promise<any[]> {
    const registeredRepositoriesParamName = `${config.deploymentPrefix}/registeredRepositories`;
    const client = new SSMClient({ region: config.region });
    const command = new GetParameterCommand({ Name: registeredRepositoriesParamName });

    return client.send(command)
        .then((response) => {
            console.log('SSM Parameter Value:', response.Parameter?.Value);
            return response.Parameter?.Value ? JSON.parse(response.Parameter.Value!) : [];
        })
        .catch((error: SSMServiceException) => {
            // Handle parameter not found separately
            if (error.name === 'ParameterNotFound') {
                console.error(`Parameter '${registeredRepositoriesParamName}' not found.`);
                return [];
            }

            // Handle other errors
            console.error('Error fetching SSM parameter:', error);
            throw error;
        });
}

(async () => {
    // Read and merge configurations
    const configData = await readAndMergeConfigs();

    // Validate and parse configuration
    const config = await validateConfig(configData);

    // Lookup and pass any previously deployed RAG configurations as an environment variable
    // so we can disallow new entries via YAML configuration.
    const ragRepositories = await getExistingRagRepositories(config);
    process.env.RAG_REPOSITORIES = JSON.stringify(ragRepositories || []);

    // Define environment
    const env: cdk.Environment = {
        account: config.accountNumber,
        region: config.region,
    };

    // Application
    const app = new cdk.App();

    new LisaServeApplicationStage(app, config.deploymentStage, {
        env: env,
        config: config,
    });

    app.synth();

})();
