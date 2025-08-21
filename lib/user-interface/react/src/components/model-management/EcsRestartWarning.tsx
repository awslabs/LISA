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

import React, { ReactElement } from 'react';
import { Alert, Checkbox, SpaceBetween } from '@cloudscape-design/components';

export type EcsRestartWarningProps = {
    acknowledged: boolean;
    onAcknowledge: (acknowledged: boolean) => void;
};

export function EcsRestartWarning (props: EcsRestartWarningProps): ReactElement {
    const { acknowledged, onAcknowledge } = props;

    return (
        <Alert
            type='warning'
            header='Container Restart Required'
            action={
                <Checkbox
                    checked={acknowledged}
                    onChange={({ detail }) => onAcknowledge(detail.checked)}
                >
                    I understand that this update will cause a temporary service outage.
                </Checkbox>
            }
        >
            <SpaceBetween size='xs'>
                <p>
                    Your container configuration changes require restarting the ECS container that is hosting the model.
                    This will cause a temporary outage for users. Users will be unable to prompt the model until the container has fully restarted, and may receive errors.
                    You can move forward with the restart, or cancel and make these changes later.
                </p>
                <p>
                    <strong>Expected Impact:</strong> Brief service interruption during container deployment.
                </p>
            </SpaceBetween>
        </Alert>
    );
}

export default EcsRestartWarning;
