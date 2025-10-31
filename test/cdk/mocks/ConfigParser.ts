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

import path from 'node:path';
import * as yaml from 'js-yaml';
import fs from 'node:fs';
import { Config, ConfigFile, ConfigSchema } from '../../../lib/schema';
import { ROOT_PATH } from '../../../lib/util';

const MOCK_PATH = path.join(ROOT_PATH, 'test', 'cdk', 'mocks');
export default class ConfigParser {

    static parseConfig (configPaths = ['config-test.yaml']): Config {
        // Read configuration file
        const configData = configPaths.map((configPath) => {
            const configFilePath = path.join(MOCK_PATH, configPath);
            const configFile = yaml.load(fs.readFileSync(configFilePath, 'utf8')) as ConfigFile;
            const configEnv = configFile.env || 'dev';
            if (!configFile[configEnv]) {
                return configFile;
            }
            return configFile[configEnv];
        })
            .reduce((result, obj) => ({ ...result, ...obj }));

        // Validate and parse configuration
        let config;
        try {
            config = ConfigSchema.parse(configData);
        } catch (error) {
            if (error instanceof Error) {
                console.error('Error parsing the configuration:', error.message);
                throw new Error(`Configuration parsing failed: ${error.message}`);
            } else {
                console.error('An unexpected error occurred:', error);
                throw new Error('Configuration parsing failed: An unexpected error occurred');
            }
        }
        return config;
    }
}
