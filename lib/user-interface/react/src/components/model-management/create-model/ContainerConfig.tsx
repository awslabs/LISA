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
import { FormProps} from '../../../shared/form/form-props';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import { IContainerConfig } from '../../../shared/model/model-management.model';
import { Button, Grid, Header, Icon, SpaceBetween } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';
import { EnvironmentVariables } from '../../../shared/form/environment-variables';

export function ContainerConfig (props: FormProps<IContainerConfig>) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <Container
                header={
                    <Header variant='h2'>Memory Size & Base Image Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='Shared Memory Size' errorText={props.formErrors?.ContainerConfig?.SharedMemorySize}>
                        <Input value={props.item.SharedMemorySize.toString()} inputMode='numeric' onBlur={() => props.touchFields(['ContainerConfig.SharedMemorySize'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.SharedMemorySize': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Base Image' errorText={props.formErrors?.ContainerConfig?.BaseImage?.BaseImage}>
                        <Input value={props.item.BaseImage.BaseImage} inputMode='text' onBlur={() => props.touchFields(['ContainerConfig.BaseImage.BaseImage'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.BaseImage.BaseImage': detail.value });
                        }}/>
                    </FormField>
                    <FormField label='Path' errorText={props.formErrors?.ContainerConfig?.BaseImage?.Path}>
                        <Input value={props.item.BaseImage.Path} inputMode='text' onBlur={() => props.touchFields(['ContainerConfig.BaseImage.Path'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.BaseImage.Path': detail.value });
                        }}/>
                    </FormField>
                    <FormField label='Type' errorText={props.formErrors?.ContainerConfig?.BaseImage?.Type}>
                        <Input value={props.item.BaseImage.Type} inputMode='text' onBlur={() => props.touchFields(['ContainerConfig.BaseImage.Type'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.BaseImage.Type': detail.value });
                        }}/>
                    </FormField>
                </SpaceBetween>
            </Container>
            <Container
                header={
                    <Header variant='h2'>Container Health Check Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='Command' errorText={props.formErrors?.ContainerConfig?.HealthCheckConfig?.Command}>
                        <SpaceBetween size={'s'}>
                            {props.item.HealthCheckConfig.Command.map((item, index) =>
                                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} key={`health-check-config-command-${index}-grid`}>
                                    <Input value={item} inputMode='text' key={`health-check-config-command-${index}`} onBlur={() => props.touchFields(['ContainerConfig.HealthCheckConfig.Command'])} onChange={({ detail }) => {
                                        props.setFields({ 'ContainerConfig.HealthCheckConfig.Command' : props.item.HealthCheckConfig.Command.map((item, i) => i === index ? detail.value : item) });
                                    }}/>
                                    <Button
                                        key={`health-check-config-command-${index}-remove-button`}
                                        onClick={() => {
                                            props.touchFields(['ContainerConfig.HealthCheckConfig.Command']);
                                            props.item.HealthCheckConfig.Command.splice(index, 1);
                                            props.setFields({'ContainerConfig.HealthCheckConfig.Command': props.item.HealthCheckConfig.Command });
                                        }}
                                        ariaLabel={'Remove command element'}
                                    >
                                        <Icon name='close' key={`health-check-config-command-${index}-icon`} />
                                    </Button>
                                </Grid>
                            )}
                            <Button
                                onClick={() => {
                                    props.setFields({'ContainerConfig.HealthCheckConfig.Command': [...props.item.HealthCheckConfig.Command, '']});
                                    props.touchFields(['ContainerConfig.HealthCheckConfig.Command']);
                                }}
                                ariaLabel={'Add command element'}
                            >
                                Add
                            </Button>
                        </SpaceBetween>
                    </FormField>
                    <FormField label='Interval' errorText={props.formErrors?.ContainerConfig?.HealthCheckConfig?.Interval}>
                        <Input value={props.item.HealthCheckConfig.Interval.toString()} inputMode='numeric' onBlur={() => props.touchFields(['ContainerConfig.HealthCheckConfig.Interval'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.HealthCheckConfig.Interval': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Start Period' errorText={props.formErrors?.ContainerConfig?.HealthCheckConfig?.StartPeriod}>
                        <Input value={props.item.HealthCheckConfig.StartPeriod.toString()} inputMode='numeric' onBlur={() => props.touchFields(['ContainerConfig.HealthCheckConfig.StartPeriod'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.HealthCheckConfig.StartPeriod': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Timeout' errorText={props.formErrors?.ContainerConfig?.HealthCheckConfig?.Timeout}>
                        <Input value={props.item.HealthCheckConfig.Timeout.toString()} inputMode='numeric' onBlur={() => props.touchFields(['ContainerConfig.HealthCheckConfig.Timeout'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.HealthCheckConfig.Timeout': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Retries' errorText={props.formErrors?.ContainerConfig?.HealthCheckConfig?.Retries}>
                        <Input value={props.item.HealthCheckConfig.Retries.toString()} inputMode='numeric' onBlur={() => props.touchFields(['ContainerConfig.HealthCheckConfig.Retries'])} onChange={({ detail }) => {
                            props.setFields({ 'ContainerConfig.HealthCheckConfig.Retries': Number(detail.value) });
                        }}/>
                    </FormField>
                </SpaceBetween>
            </Container>
            <Container
                header={
                    <Header variant='h2'>Container Environment</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <EnvironmentVariables item={props.item} setFields={props.setFields} touchFields={props.touchFields} formErrors={props.formErrors} propertyPath={['ContainerConfig', 'Environment']}/>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
