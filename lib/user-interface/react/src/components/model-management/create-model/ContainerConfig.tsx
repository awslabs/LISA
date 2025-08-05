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

type ContainerConfigProps = FormProps<IContainerConfig> & {
    isEdit: boolean;
};

export function ContainerConfig (props: ContainerConfigProps) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <Container
                header={
                    <Header variant='h2'>Memory Size & Image Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='Shared Memory Size' errorText={props.formErrors?.containerConfig?.sharedMemorySize}>
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input 
                                value={props.item.sharedMemorySize.toString()} 
                                type='number' 
                                inputMode='numeric' 
                                disabled={props.isEdit}
                                onBlur={() => props.touchFields(['containerConfig.sharedMemorySize'])} 
                                onChange={({ detail }) => {
                                    props.setFields({ 'containerConfig.sharedMemorySize': Number(detail.value) });
                                }}
                            />
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>MiB</span>
                        </Grid>
                    </FormField>
                    <FormField label='Base Image' errorText={props.formErrors?.containerConfig?.image?.baseImage}>
                        <Input 
                            value={props.item.image.baseImage} 
                            inputMode='text' 
                            disabled={props.isEdit}
                            onBlur={() => props.touchFields(['containerConfig.image.baseImage'])} 
                            onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.image.baseImage': detail.value });
                            }}
                        />
                    </FormField>
                    <FormField label='Type' errorText={props.formErrors?.containerConfig?.image?.type}>
                        <Input 
                            value={props.item.image.type} 
                            inputMode='text' 
                            disabled={props.isEdit}
                            onBlur={() => props.touchFields(['containerConfig.image.type'])} 
                            onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.image.type': detail.value });
                            }}
                        />
                    </FormField>
                </SpaceBetween>
            </Container>
            <Container
                header={
                    <Header variant='h2'>Container Health Check Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='Command' errorText={props.formErrors?.containerConfig?.healthCheckConfig?.command}>
                        <SpaceBetween size={'s'}>
                            {props.item.healthCheckConfig.command.map((item, index) =>
                                <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]} key={`health-check-config-command-${index}-grid`}>
                                    <Input value={item} inputMode='text' key={`health-check-config-command-${index}`} onBlur={() => props.touchFields(['containerConfig.healthCheckConfig.command'])} onChange={({ detail }) => {
                                        props.setFields({ 'containerConfig.healthCheckConfig.command' : props.item.healthCheckConfig.command.map((item, i) => i === index ? detail.value : item) });
                                    }}/>
                                    <Button
                                        key={`health-check-config-command-${index}-remove-button`}
                                        onClick={() => {
                                            props.touchFields(['containerConfig.healthCheckConfig.command']);
                                            props.item.healthCheckConfig.command.splice(index, 1);
                                            props.setFields({'containerConfig.healthCheckConfig.command': props.item.healthCheckConfig.command });
                                        }}
                                        ariaLabel={'Remove command element'}
                                    >
                                        <Icon name='close' key={`health-check-config-command-${index}-icon`} />
                                    </Button>
                                </Grid>
                            )}
                            <Button
                                onClick={() => {
                                    props.setFields({'containerConfig.healthCheckConfig.command': [...props.item.healthCheckConfig.command, '']});
                                    props.touchFields(['containerConfig.healthCheckConfig.command']);
                                }}
                                ariaLabel={'Add command element'}
                            >
                                Add
                            </Button>
                        </SpaceBetween>
                    </FormField>
                    <FormField label='Interval' errorText={props.formErrors?.containerConfig?.healthCheckConfig?.interval}>
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.healthCheckConfig.interval.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['containerConfig.healthCheckConfig.interval'])} onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.healthCheckConfig.interval': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField label='Start Period' errorText={props.formErrors?.containerConfig?.healthCheckConfig?.startPeriod}>
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.healthCheckConfig.startPeriod.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['containerConfig.healthCheckConfig.startPeriod'])} onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.healthCheckConfig.startPeriod': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField label='Timeout' errorText={props.formErrors?.containerConfig?.healthCheckConfig?.timeout}>
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.healthCheckConfig.timeout.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['containerConfig.healthCheckConfig.timeout'])} onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.healthCheckConfig.timeout': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField label='Retries' errorText={props.formErrors?.containerConfig?.healthCheckConfig?.retries}>
                        <Input value={props.item.healthCheckConfig.retries.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['containerConfig.healthCheckConfig.retries'])} onChange={({ detail }) => {
                            props.setFields({ 'containerConfig.healthCheckConfig.retries': Number(detail.value) });
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
                    <EnvironmentVariables item={props.item} setFields={props.setFields} touchFields={props.touchFields} formErrors={props.formErrors} propertyPath={['containerConfig', 'environment']}/>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
