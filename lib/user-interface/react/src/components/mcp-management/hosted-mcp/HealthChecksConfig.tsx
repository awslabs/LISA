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
import {
    Container,
    FormField,
    Grid,
    Header,
    Input,
    SpaceBetween,
} from '@cloudscape-design/components';
import { SetFieldsFunction, TouchFieldsFunction } from '@/shared/validation';
import { HostedMcpServerRequestForm } from '@/shared/model/hosted-mcp-server.model';

type HealthChecksConfigProps = {
    item: HostedMcpServerRequestForm;
    setFields: SetFieldsFunction;
    touchFields: TouchFieldsFunction;
    formErrors: any;
};

export function HealthChecksConfig ({
    item,
    setFields,
    formErrors,
}: HealthChecksConfigProps): ReactElement {
    const containerHC = item.containerHealthCheckConfig;
    const lbHC = item.loadBalancerConfig?.healthCheckConfig;

    return (
        <SpaceBetween size='s'>
            <Container header={<Header variant='h2'>Container Health Check</Header>}>
                <SpaceBetween size='s'>
                    <FormField
                        label='Command'
                        description='Command executed inside the container to verify health. Use {{PORT}} to reference the container port.'
                        errorText={formErrors?.containerHealthCheckConfig?.command}
                    >
                        <Input
                            value={
                                Array.isArray(containerHC?.command)
                                    ? containerHC.command.join(' ')
                                    : containerHC?.command || ''
                            }
                            onChange={({ detail }) =>
                                setFields({ 'containerHealthCheckConfig.command': detail.value })
                            }
                            placeholder='CMD-SHELL exit 0'
                        />
                    </FormField>
                    <FormField
                        label='Interval'
                        description='Time between running the health check.'
                        errorText={formErrors?.containerHealthCheckConfig?.interval}
                    >
                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                            <Input
                                value={containerHC?.interval?.toString() || ''}
                                onChange={({ detail }) => {
                                    const value = detail.value ? Number(detail.value) : undefined;
                                    setFields({ 'containerHealthCheckConfig.interval': value });
                                }}
                                inputMode='numeric'
                                type='number'
                            />
                            <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Timeout'
                        description='Time to wait for a health check to succeed before considering it failed.'
                        errorText={formErrors?.containerHealthCheckConfig?.timeout}
                    >
                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                            <Input
                                value={containerHC?.timeout?.toString() || ''}
                                onChange={({ detail }) => {
                                    const value = detail.value ? Number(detail.value) : undefined;
                                    setFields({ 'containerHealthCheckConfig.timeout': value });
                                }}
                                inputMode='numeric'
                                type='number'
                            />
                            <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Retries'
                        description='Number of times to retry a failed health check before the container is considered unhealthy.'
                        errorText={formErrors?.containerHealthCheckConfig?.retries}
                    >
                        <Input
                            value={containerHC?.retries?.toString() || ''}
                            onChange={({ detail }) => {
                                const value = detail.value ? Number(detail.value) : undefined;
                                setFields({ 'containerHealthCheckConfig.retries': value });
                            }}
                            inputMode='numeric'
                            type='number'
                        />
                    </FormField>
                    <FormField
                        label='Start period'
                        description='Grace period before failed health checks count towards the maximum number of retries.'
                        errorText={formErrors?.containerHealthCheckConfig?.startPeriod}
                    >
                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                            <Input
                                value={containerHC?.startPeriod?.toString() || ''}
                                onChange={({ detail }) => {
                                    const value = detail.value ? Number(detail.value) : undefined;
                                    setFields({ 'containerHealthCheckConfig.startPeriod': value });
                                }}
                                inputMode='numeric'
                                type='number'
                            />
                            <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                        </Grid>
                    </FormField>
                </SpaceBetween>
            </Container>
            <Container header={<Header variant='h2'>Load Balancer Health Check</Header>}>
                <SpaceBetween size='s'>
                    <FormField
                        label='Path'
                        description='Relative path used by the load balancer to determine service health.'
                        errorText={formErrors?.loadBalancerConfig?.healthCheckConfig?.path}
                    >
                        <Input
                            value={lbHC?.path || ''}
                            onChange={({ detail }) =>
                                setFields({ 'loadBalancerConfig.healthCheckConfig.path': detail.value })
                            }
                            placeholder='/status'
                        />
                    </FormField>
                    <FormField
                        label='Interval'
                        description='Time between health checks.'
                        errorText={formErrors?.loadBalancerConfig?.healthCheckConfig?.interval}
                    >
                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                            <Input
                                value={lbHC?.interval?.toString() || ''}
                                onChange={({ detail }) => {
                                    const value = detail.value ? Number(detail.value) : undefined;
                                    setFields({ 'loadBalancerConfig.healthCheckConfig.interval': value });
                                }}
                                inputMode='numeric'
                                type='number'
                            />
                            <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Timeout'
                        description='Time to wait for a response before considering the health check failed.'
                        errorText={formErrors?.loadBalancerConfig?.healthCheckConfig?.timeout}
                    >
                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} disableGutters={true}>
                            <Input
                                value={lbHC?.timeout?.toString() || ''}
                                onChange={({ detail }) => {
                                    const value = detail.value ? Number(detail.value) : undefined;
                                    setFields({ 'loadBalancerConfig.healthCheckConfig.timeout': value });
                                }}
                                inputMode='numeric'
                                type='number'
                            />
                            <span style={{ lineHeight: '2.5em', paddingLeft: '0.5em' }}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Healthy threshold'
                        description='Number of consecutive successful health checks before considering the target healthy.'
                        errorText={formErrors?.loadBalancerConfig?.healthCheckConfig?.healthyThresholdCount}
                    >
                        <Input
                            value={lbHC?.healthyThresholdCount?.toString() || ''}
                            onChange={({ detail }) => {
                                const value = detail.value ? Number(detail.value) : undefined;
                                setFields({
                                    'loadBalancerConfig.healthCheckConfig.healthyThresholdCount': value,
                                });
                            }}
                            inputMode='numeric'
                            type='number'
                        />
                    </FormField>
                    <FormField
                        label='Unhealthy threshold'
                        description='Number of consecutive failed health checks before considering the target unhealthy.'
                        errorText={formErrors?.loadBalancerConfig?.healthCheckConfig?.unhealthyThresholdCount}
                    >
                        <Input
                            value={lbHC?.unhealthyThresholdCount?.toString() || ''}
                            onChange={({ detail }) => {
                                const value = detail.value ? Number(detail.value) : undefined;
                                setFields({
                                    'loadBalancerConfig.healthCheckConfig.unhealthyThresholdCount': value,
                                });
                            }}
                            inputMode='numeric'
                            type='number'
                        />
                    </FormField>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
