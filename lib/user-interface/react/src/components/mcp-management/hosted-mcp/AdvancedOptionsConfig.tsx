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

import { ReactElement } from 'react';
import { FormField, Grid, Input, SpaceBetween } from '@cloudscape-design/components';
import { SetFieldsFunction, TouchFieldsFunction } from '@/shared/validation';
import { HostedMcpServerRequestForm } from '@/shared/model/hosted-mcp-server.model';
import { EnvironmentVariables } from '@/shared/form/environment-variables';

type AdvancedOptionsConfigProps = {
    item: HostedMcpServerRequestForm;
    setFields: SetFieldsFunction;
    touchFields: TouchFieldsFunction;
    formErrors: any;
    isEdit: boolean;
};

export function AdvancedOptionsConfig ({
    item,
    setFields,
    touchFields,
    formErrors,
    isEdit,
}: AdvancedOptionsConfigProps): ReactElement {
    return (
        <SpaceBetween size='s'>
            <FormField
                label='S3 artifact path'
                description='S3 URI for server artifacts.'
            >
                <Input
                    value={item.s3Path || ''}
                    onChange={({ detail }) => setFields({ s3Path: detail.value })}
                    placeholder='s3://bucket/path'
                    disabled={isEdit}
                />
            </FormField>
            <FormField
                label='CPU'
                description='Defaults to 256 units (0.25 vCPU).'
            >
                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                    <Input
                        value={item.cpu?.toString() || ''}
                        onChange={({ detail }) => {
                            const value = detail.value ? Number(detail.value) : undefined;
                            setFields({ cpu: value });
                        }}
                        inputMode='numeric'
                        type='number'
                    />
                    <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>units</span>
                </Grid>
            </FormField>
            <FormField
                label='Memory'
                description='Defaults to 512 MiB.'
            >
                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                    <Input
                        value={item.memoryLimitMiB?.toString() || ''}
                        onChange={({ detail }) => {
                            const value = detail.value ? Number(detail.value) : undefined;
                            setFields({ memoryLimitMiB: value });
                        }}
                        inputMode='numeric'
                        type='number'
                    />
                    <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>MiB</span>
                </Grid>
            </FormField>
            <FormField
                label='Task execution role ARN'
                description='IAM role for pulling images and reading S3.'
            >
                <Input
                    value={item.taskExecutionRoleArn || ''}
                    onChange={({ detail }) => setFields({ taskExecutionRoleArn: detail.value })}
                    disabled={isEdit}
                    placeholder='arn:aws:iam::1234567890:role/task-executor-role'
                />
            </FormField>
            <FormField
                label='Task role ARN'
                description='IAM role for the running task.'
            >
                <Input
                    value={item.taskRoleArn || ''}
                    onChange={({ detail }) => setFields({ taskRoleArn: detail.value })}
                    disabled={isEdit}
                    placeholder='arn:aws:iam::1234567890:role/task-role'
                />
            </FormField>
            <EnvironmentVariables
                item={{ environment: item.environment }}
                setFields={setFields}
                touchFields={touchFields}
                formErrors={formErrors}
                propertyPath={['environment']}
            />
        </SpaceBetween>
    );
}
