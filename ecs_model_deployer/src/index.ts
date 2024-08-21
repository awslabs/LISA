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

import { spawnSync, spawn } from 'child_process';
import { readdirSync, symlinkSync, rmSync } from 'fs';

const ACTION_DEPLOY = 'deploy';
const ACTION_DESTROY = 'destroy';

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
            }
        }
    }

    process.chdir('/tmp/');
};

export const handler = async (event: any) => {
    if (!event.action) {
        console.log(`action not provided in ${JSON.stringify(event)}`);
        throw new Error('action not provided');
    } else if ( ![ACTION_DESTROY, ACTION_DEPLOY].includes(event.action) ) {
        console.log(`Invalid action ${event.action}`);
        throw new Error(`Invalid action ${event.action}`);
    }

    if (!event.modelConfig) {
        console.log(`modelConfig not provided in ${JSON.stringify(event)}`);
        throw new Error('modeConfig not provided');
    }
    const modelConfig = event.modelConfig;
    process.env['LISA_MODEL_CONFIG'] = JSON.stringify(modelConfig);

    if (!process.env['LISA_CONFIG']) {
        console.log('LISA_CONFIG environment variable not set');
        throw new Error('LISA_CONFIG environment variable not set');
    }
    const config = JSON.parse(process.env['LISA_CONFIG']!);

    createWritableEnv();

    const ret = spawnSync('./node_modules/aws-cdk/bin/cdk', ['synth', '-o', '/tmp/cdk.out']);

    let stderr = String(ret.output[2]);
    if ( ret.status !== 0 ) {
        console.log(`cdk synth failed with stderr: ${stderr}`);
        throw new Error('Stack failed to synthesize');
    }


    const stackName = `${config.deploymentName}-${modelConfig.modelId}`;
    if ( event.action === ACTION_DEPLOY ) {
        const deploy_promise: Promise<Number> = new Promise( (resolve) => {
            const cp = spawn('./node_modules/aws-cdk/bin/cdk', ['deploy', stackName, '-o', '/tmp/cdk.out']);

            cp.on('close', (code) => {
                resolve(code ?? -1);
            });

            setTimeout(() => {
                console.log('60 second timeout');
                resolve(0);
            }, 60 * 1000);
        });

        const exitCode = await deploy_promise;
        stderr = String(ret.output[2]);
        if ( exitCode !== 0 ) {
            console.log(`cdk deploy failed with stderr: ${stderr}`);
            throw new Error('Stack failed to deploy');
        }
    } else if ( event.action === ACTION_DESTROY ) {
        const deploy_promise: Promise<Number> = new Promise( (resolve) => {
            const cp = spawn('./node_modules/aws-cdk/bin/cdk', ['destroy', '-f', stackName, '-o', '/tmp/cdk.out']);

            cp.on('close', (code) => {
                resolve(code ?? -1);
            });

            setTimeout(() => {
                console.log('60 second timeout');
                resolve(0);
            }, 60 * 1000);
        });

        const exitCode = await deploy_promise;
        stderr = String(ret.output[2]);
        if ( exitCode !== 0 ) {
            console.log(`cdk destroy failed with stderr: ${stderr}`);
            throw new Error('Stack failed to destroy');
        }
    }
    return stackName;
};
