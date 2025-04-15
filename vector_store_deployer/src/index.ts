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

import { ChildProcess, spawn, spawnSync } from 'node:child_process';
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

    const deploy_promise: Promise<ChildProcess | undefined> = new Promise( (resolve) => {
        const cp = spawn('./node_modules/aws-cdk/bin/cdk', ['deploy', stackName, '-o', '/tmp/cdk.out'], {
            env: {...process.env},
            stdio: 'inherit'
        });

        cp.on('exit', (code, signal) => {
            console.log(`Process exited with code: ${code}, signal: ${signal}`);
        });

        cp.on('close', (code, signal) => {
            console.log(`Process closed with code: ${code}, signal: ${signal}`);
        });

        cp.on('error', (err) => {
            console.error(`Failed to start process: ${err.message}`);
        });

        setTimeout(() => {
            console.warn('14 minute timeout');
            resolve(undefined);
        }, 840 * 1000);
    });

    const cp = await deploy_promise;
    if ( cp ) {
        if ( cp.exitCode !== 0 ) {
            throw new Error('Stack failed to deploy');
        }
    }

    return {stackName: stackName};
};
