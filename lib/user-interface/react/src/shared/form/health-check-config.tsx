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
import { Button, Container, FormField, Grid, Header, Icon, Input, SpaceBetween } from '@cloudscape-design/components';
import { FormProps } from './form-props';

export type HealthCheckConfigProps = FormProps<{
    command: string[];
    interval: number;
    timeout: number;
    retries: number;
    startPeriod: number;
}> & {
    propertyPath: string[];
};

export function HealthCheckConfig (props: HealthCheckConfigProps): ReactElement {
    const { item, setFields, touchFields, formErrors, propertyPath } = props;
    const basePath = propertyPath.join('.');

    return (
        <Container
            header={
                <Header variant='h2'>Container Health Check Config</Header>
            }
        >
            <SpaceBetween size='s'>
                <FormField 
                    label='Command'
                    description='Health check command executed inside the container. Multiple command parts can be added.'
                    errorText={formErrors?.[propertyPath[0]]?.[propertyPath[1]]?.command}
                >
                    <SpaceBetween size='s'>
                        {item.command.map((cmdItem, index) =>
                            <Grid 
                                gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} 
                                key={`health-check-config-command-${index}-grid`}
                                disableGutters={true}
                            >
                                <Input 
                                    value={cmdItem} 
                                    inputMode='text' 
                                    key={`health-check-config-command-${index}`} 
                                    onBlur={() => touchFields([`${basePath}.command`])} 
                                    onChange={({ detail }) => {
                                        setFields({ 
                                            [`${basePath}.command`]: item.command.map((item, i) => 
                                                i === index ? detail.value : item
                                            ) 
                                        });
                                    }}
                                />
                                <Button
                                    key={`health-check-config-command-${index}-remove-button`}
                                    onClick={() => {
                                        touchFields([`${basePath}.command`]);
                                        item.command.splice(index, 1);
                                        setFields({ [`${basePath}.command`]: item.command });
                                    }}
                                    ariaLabel='Remove command element'
                                >
                                    <Icon name='close' key={`health-check-config-command-${index}-icon`} />
                                </Button>
                            </Grid>
                        )}
                        <Button
                            onClick={() => {
                                setFields({ [`${basePath}.command`]: [...item.command, ''] });
                                touchFields([`${basePath}.command`]);
                            }}
                            ariaLabel='Add command element'
                        >
                            Add
                        </Button>
                    </SpaceBetween>
                </FormField>
                <FormField 
                    label='Interval'
                    description='Time between running the health check.'
                    errorText={formErrors?.[propertyPath[0]]?.[propertyPath[1]]?.interval}
                >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input 
                            value={item.interval.toString()} 
                            type='number' 
                            inputMode='numeric' 
                            onBlur={() => touchFields([`${basePath}.interval`])} 
                            onChange={({ detail }) => {
                                setFields({ [`${basePath}.interval`]: Number(detail.value) });
                            }}
                        />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </FormField>
                <FormField 
                    label='Start Period'
                    description='Grace period before failed health checks count towards the maximum number of retries.'
                    errorText={formErrors?.[propertyPath[0]]?.[propertyPath[1]]?.startPeriod}
                >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input 
                            value={item.startPeriod.toString()} 
                            type='number' 
                            inputMode='numeric' 
                            onBlur={() => touchFields([`${basePath}.startPeriod`])} 
                            onChange={({ detail }) => {
                                setFields({ [`${basePath}.startPeriod`]: Number(detail.value) });
                            }}
                        />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </FormField>
                <FormField 
                    label='Timeout'
                    description='Time to wait for a health check to succeed before considering it failed.'
                    errorText={formErrors?.[propertyPath[0]]?.[propertyPath[1]]?.timeout}
                >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input 
                            value={item.timeout.toString()} 
                            type='number' 
                            inputMode='numeric' 
                            onBlur={() => touchFields([`${basePath}.timeout`])} 
                            onChange={({ detail }) => {
                                setFields({ [`${basePath}.timeout`]: Number(detail.value) });
                            }}
                        />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </FormField>
                <FormField 
                    label='Retries'
                    description='Number of times to retry a failed health check before the container is considered unhealthy.'
                    errorText={formErrors?.[propertyPath[0]]?.[propertyPath[1]]?.retries}
                >
                    <Input 
                        value={item.retries.toString()} 
                        type='number' 
                        inputMode='numeric' 
                        onBlur={() => touchFields([`${basePath}.retries`])} 
                        onChange={({ detail }) => {
                            setFields({ [`${basePath}.retries`]: Number(detail.value) });
                        }}
                    />
                </FormField>
            </SpaceBetween>
        </Container>
    );
}
