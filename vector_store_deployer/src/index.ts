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

import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, readdirSync, rmSync, symlinkSync } from 'node:fs';

/*
  cdk CLI always wants ./ to be writable in order to write cdk.context.json.
  This should really be an environment variable or something, but this function
  should give us a writable ./ without wasting tons of compute time to copy
*/
const createWritableEnv = () => {
    rmSync('/tmp/cdk.out', {recursive: true, force: true});
    const files = readdirSync('.');
    for ( const f of files ) {
        /*
          We want this file to be empty or absent so that any info needed is
          pulled from the account instead of the cache
        */
        if ( f === 'cdk.context.json' ) {
            continue;
        }
        const source = `/tmp/${f}`;
        const target = `${process.env['PWD']}/${f}`;

        try {
            symlinkSync(target, source, 'file');
        } catch ( err ) {
            if ( err instanceof Error && err.message.match(/EEXIST/) ) {
                // Writable env already established from previous call.
            } else {
                throw err;
            }
        }
    }
    mkdirSync('/tmp/cdk.out', {recursive: true});

    process.chdir('/tmp/');
};

export const handler = async (event: any) => {
    console.log(`Event payload: ${JSON.stringify(event)}`);

    if (!event.ragConfig) {
        console.log(`ragConfig not provided in ${JSON.stringify(event)}`);
        throw new Error('ragConfig not provided');
    }
    const ragConfig = event.ragConfig;
    process.env['LISA_RAG_CONFIG'] = JSON.stringify(ragConfig);

    if (!process.env['LISA_CONFIG']) {
        console.log('LISA_CONFIG environment variable not set');
        throw new Error('LISA_CONFIG environment variable not set');
    }
    const config = JSON.parse(process.env['LISA_CONFIG']!);

    createWritableEnv();

    const stackName = [config.appName, config.deploymentName, config.deploymentStage, 'vector-store', ragConfig.repositoryId].join('-');
    process.env['LISA_STACK_NAME'] = stackName;

    const ret = spawnSync('./node_modules/aws-cdk/bin/cdk', ['synth', '-o', '/tmp/cdk.out'], {stdio: 'inherit'});
    if ( ret.status !== 0 ) {
        throw new Error('Stack failed to synthesize');
    }

    const deploy_promise: Promise<number> = new Promise( (resolve, reject) => {
        const cp = spawn('./node_modules/aws-cdk/bin/cdk', ['deploy', stackName, '-o', '/tmp/cdk.out'], {
            env: {...process.env},
            stdio: 'inherit'
        });

        cp.on('exit', (code, signal) => {
            console.log(`Process exited with code: ${code}, signal: ${signal}`);
            if (code === 0) {
                resolve(code!);
            } else {
                reject(new Error(`CDK deploy failed with code ${code}`));
            }
        });

        cp.on('error', (err) => {
            console.error(`Failed to start process: ${err.message}`);
            reject(err);
        });

        setTimeout(() => {
            console.log(`180s timeout - Disconnecting from CloudFormation ${stackName} stack monitoring from Lambda`);
            resolve(0);
        }, 180 * 1000);
    });

    try {
        await deploy_promise;

        // Check if ragConfig is for Bedrock KB without pipelines
        if (ragConfig.type === 'bedrock_knowledge_base' && (!ragConfig.pipelines || ragConfig.pipelines.length === 0)) {
            console.log('Bedrock KB repository without pipelines - no stack created');
            return { stackName: null };
        }

        return { stackName: stackName };
    } catch (error) {
        console.error('Deployment failed:', error);
        throw error;
    }
};
