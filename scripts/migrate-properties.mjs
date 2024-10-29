/**
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the 'License').
 You may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an 'AS IS' BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */

import * as yaml from 'js-yaml';
import fs from 'fs';
import path from 'path';
import _ from 'lodash';

console.log('MIGRATING PROPERTIES...');

const configFilePath = path.join('./config.yaml');
const configFile = yaml.load(fs.readFileSync(configFilePath, 'utf8'));

console.log('FOUND CONFIG FILE: config.yaml\n')

for (const key in configFile){
  if(_.isPlainObject(configFile[key])) {
     const oldConfig = configFile[key]
     let newConfig = {...configFile[key]};

     delete newConfig.lambdaConfig;
     delete newConfig.litellmConfig;
     delete newConfig.restApiConfig;

     newConfig['restApiConfig'] = {
       'sslCertIamArn': oldConfig['restApiConfig']['loadBalancerConfig']['sslCertIamArn'],
       'internetFacing': oldConfig['restApiConfig']['internetFacing'],
       'domainName': oldConfig['restApiConfig']['loadBalancerConfig']['domainName'],
       'rdsConfig': oldConfig['restApiConfig']['rdsConfig'],
     }

     newConfig['litellmConfig'] = {
       'dbKey': oldConfig['litellmConfig']['general_settings']['master_key']
     }

     if (JSON.stringify(newConfig.restApiConfig) === '{}'){
         delete newConfig.restApiConfig;
     }

      if (JSON.stringify(newConfig.litellmConfig) === '{}'){
          delete newConfig.litellmConfig;
      }

     console.log('NEW CONFIG FILE = \n' + yaml.dump(_(newConfig).omit(_.isNil).value()));
     fs.writeFileSync('./config-custom.yaml', yaml.dump(_(newConfig).omit(_.isNil).value()));
  }
}
