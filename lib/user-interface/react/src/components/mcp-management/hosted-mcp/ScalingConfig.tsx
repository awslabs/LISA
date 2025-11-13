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

type ScalingConfigProps = {
    item: HostedMcpServerRequestForm;
    setFields: SetFieldsFunction;
    touchFields: TouchFieldsFunction;
    formErrors: any;
};

export function ScalingConfig ({ item, setFields, touchFields, formErrors }: ScalingConfigProps): ReactElement {
    return (
        <SpaceBetween size='s'>
            <FormField
                label='Minimum capacity'
                description='Minimum number of tasks to maintain.'
                errorText={formErrors?.autoScalingConfig?.minCapacity}
            >
                <Input
                    value={item.autoScalingConfig.minCapacity.toString()}
                    onChange={({ detail }) => {
                        const value = Number(detail.value);
                        setFields({ 'autoScalingConfig.minCapacity': value });
                    }}
                    onBlur={() => touchFields(['autoScalingConfig.minCapacity'])}
                    inputMode='numeric'
                    type='number'
                />
            </FormField>
            <FormField
                label='Maximum capacity'
                description='Maximum number of tasks allowed to scale to.'
                errorText={formErrors?.autoScalingConfig?.maxCapacity}
            >
                <Input
                    value={item.autoScalingConfig.maxCapacity.toString()}
                    onChange={({ detail }) => {
                        const value = Number(detail.value);
                        setFields({ 'autoScalingConfig.maxCapacity': value });
                    }}
                    onBlur={() => touchFields(['autoScalingConfig.maxCapacity'])}
                    inputMode='numeric'
                    type='number'
                />
            </FormField>
            <FormField
                label='Target value'
                description='Target metric value for scaling.'
            >
                <Input
                    value={item.autoScalingConfig.targetValue?.toString() || ''}
                    onChange={({ detail }) => {
                        const value = detail.value ? Number(detail.value) : undefined;
                        setFields({ 'autoScalingConfig.targetValue': value });
                    }}
                    inputMode='numeric'
                    type='number'
                />
            </FormField>
            <FormField
                label='Metric name'
                description='CloudWatch metric for scaling, e.g. RequestCount.'
            >
                <Input
                    value={item.autoScalingConfig.metricName || ''}
                    onChange={({ detail }) => setFields({ 'autoScalingConfig.metricName': detail.value })}
                />
            </FormField>
            <FormField
                label='Scale duration'
                description='Period length for the CloudWatch metric.'
            >
                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                    <Input
                        value={item.autoScalingConfig.duration?.toString() || ''}
                        onChange={({ detail }) => {
                            const value = detail.value ? Number(detail.value) : undefined;
                            setFields({ 'autoScalingConfig.duration': value });
                        }}
                        inputMode='numeric'
                        type='number'
                    />
                    <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                </Grid>
            </FormField>
            <FormField
                label='Cooldown'
                description='Cooldown between scaling events.'
            >
                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                    <Input
                        value={item.autoScalingConfig.cooldown?.toString() || ''}
                        onChange={({ detail }) => {
                            const value = detail.value ? Number(detail.value) : undefined;
                            setFields({ 'autoScalingConfig.cooldown': value });
                        }}
                        inputMode='numeric'
                        type='number'
                    />
                    <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                </Grid>
            </FormField>
        </SpaceBetween>
    );
}
