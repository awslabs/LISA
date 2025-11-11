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
import { Container, Grid, Header, Select, SpaceBetween } from '@cloudscape-design/components';
import { EnvironmentVariables } from '../../../shared/form/environment-variables';
import { HealthCheckConfig } from '../../../shared/form/health-check-config';
import { EcsSourceType } from '../../../../../../schema';

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
                    <FormField 
                        label='Shared Memory Size'
                        description='Amount of shared memory allocated to the container.'
                        errorText={props.formErrors?.containerConfig?.sharedMemorySize}
                    >
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input
                            value={props.item.sharedMemorySize.toString()}
                            type='number'
                            inputMode='numeric'
                            onBlur={() => props.touchFields(['containerConfig.sharedMemorySize'])}
                            onChange={({ detail }) => {
                                props.setFields({ 'containerConfig.sharedMemorySize': Number(detail.value) });
                            }}
                        />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>MiB</span>
                    </Grid>
                    <FormField 
                        label='Base Image'
                        description='Base container image used to build model hosting image, e.g. vllm/vllm-openai'
                        errorText={props.formErrors?.containerConfig?.image?.baseImage}
                    >
                    </FormField>
                    <Input
                        value={props.item.image.baseImage}
                        inputMode='text'
                        disabled={props.isEdit}
                        onBlur={() => props.touchFields(['containerConfig.image.baseImage'])}
                        onChange={({ detail }) => {
                            props.setFields({ 'containerConfig.image.baseImage': detail.value });
                        }}
                    />
                    <FormField 
                        label='Type' 
                        description='Type of container image source.'
                        errorText={props.formErrors?.inferenceContainer}
                    >
                    </FormField>
                    <Select
                        selectedOption={{label: props.item.image.type, value: props.item.image.type}}
                        onBlur={() => props.touchFields(['containerConfig.image.type'])}
                        onChange={({ detail }) => {
                            props.setFields({ 'containerConfig.image.type': detail.selectedOption.value });
                        }}
                        options={[
                            { label: 'asset', value: EcsSourceType.ASSET, description: 'Base container image used to build model hosting image, e.g. \'vllm/vllm-openai\'' },
                            { label: 'ecr', value: EcsSourceType.ECR, description: 'Prebuilt ECR image url used when deploying to ECS' },
                        ]}
                    />
                </SpaceBetween>
            </Container>
            <HealthCheckConfig 
                item={props.item.healthCheckConfig} 
                setFields={props.setFields} 
                touchFields={props.touchFields} 
                formErrors={props.formErrors}
                propertyPath={['containerConfig', 'healthCheckConfig']}
            />
            <Container
                header={
                    <Header variant='h2'>Container Environment</Header>
                }
            >
                <SpaceBetween size='s'>
                    <EnvironmentVariables item={props.item} setFields={props.setFields} touchFields={props.touchFields} formErrors={props.formErrors} propertyPath={['containerConfig', 'environment']}/>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
