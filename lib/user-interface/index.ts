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
import { Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { UserInterfaceConstruct, UserInterfaceProps } from './userInterfaceConstruct';

export * from './userInterfaceConstruct';

/**
 * User Interface Stack.
 */
export class UserInterfaceStack extends Stack {
    /**
     * @param {Construct} scope - The parent or owner of the construct.
     * @param {string} id - The unique identifier for the construct within its scope.
     * @param {UserInterfaceProps} props - The properties of the construct.
     */
    constructor (scope: Construct, id: string, props: UserInterfaceProps) {
        super(scope, id, props);
        new UserInterfaceConstruct(this, id + 'Resources', props);
    }
}
