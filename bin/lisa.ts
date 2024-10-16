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
import * as fs from 'fs';
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as yaml from 'js-yaml';

import { Config, ConfigFile, ConfigSchema } from '../lib/schema';
import { LisaServeApplicationStage } from '../lib/stages';

// Read configuration file
const configFilePath = path.join(__dirname, '../config.yaml');
const configFile = yaml.load(fs.readFileSync(configFilePath, 'utf8')) as ConfigFile;
let configEnv = configFile.env || 'dev';

// Select configuration environment
if (process.env.ENV) {
    configEnv = process.env.ENV;
}
const configData = configFile[configEnv];
if (!configData) {
    throw new Error(`Configuration for environment "${configEnv}" not found.`);
}

// Other command line argument overrides
type EnvMapping = [string, keyof Config];
const mappings: EnvMapping[] = [
    ['PROFILE', 'profile'],
    ['DEPLOYMENT_NAME', 'deploymentName'],
    ['ACCOUNT_NUMBER', 'accountNumber'],
    ['REGION', 'region'],
];
mappings.forEach(([envVar, configVar]) => {
    const envValue = process.env[envVar];
    if (envValue) {
        (configData as any)[configVar] = envValue;
    }
});

// Validate and parse configuration
let config: Config;
try {
    config = ConfigSchema.parse(configData);
} catch (error) {
    if (error instanceof Error) {
        console.error('Error parsing the configuration:', error.message);
    } else {
        console.error('An unexpected error occurred:', error);
    }
    process.exit(1);
}

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
