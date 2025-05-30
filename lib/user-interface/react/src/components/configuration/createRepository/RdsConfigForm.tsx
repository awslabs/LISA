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

import Container from '@cloudscape-design/components/container';
import { Header, SpaceBetween } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import React, { ReactElement } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import { RdsConfig as RdsConfigSchema, RdsInstanceConfig } from '#root/lib/schema';

type RdsConfigProps = {
    isEdit: boolean
};

export function RdsConfigForm (props: FormProps<RdsConfigSchema> & RdsConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    return (
        <Container header={<Header variant='h2'>PostgreSQL Config</Header>}>
            <SpaceBetween direction='vertical' size='s'>
                <FormField label='Username' key={'username'}
                    errorText={formErrors?.rdsConfig?.username}
                    description={RdsInstanceConfig.shape.username.description}>
                    <Input value={item.username} inputMode='text'
                        onBlur={() => touchFields(['rdsConfig.username'])}
                        onChange={({ detail }) => setFields({ 'rdsConfig.username': detail.value })}
                        placeholder='Username' disabled={isEdit} />
                </FormField>
                <FormField label='Password Secret Id - optional' key={'password'}
                    errorText={formErrors?.rdsConfig?.passwordSecretId}
                    description={RdsInstanceConfig.shape.passwordSecretId.description}>
                    <Input value={item.passwordSecretId} inputMode='text'
                        onBlur={() => touchFields(['rdsConfig.passwordSecretId'])}
                        onChange={({ detail }) => setFields({ 'rdsConfig.passwordSecretId': detail.value })}
                        placeholder='Password Secret Id' disabled={isEdit} />
                </FormField>
                <FormField label='Host - optional' key={'host'}
                    errorText={formErrors?.rdsConfig?.dbHost}
                    description={RdsInstanceConfig.shape.dbHost.description}>
                    <Input value={item.dbHost} inputMode='text'
                        onBlur={() => touchFields(['rdsConfig.dbHost'])}
                        onChange={({ detail }) => setFields({ 'rdsConfig.dbHost': detail.value })}
                        placeholder='rds.region.amazonaws.com ' disabled={isEdit} />
                </FormField>
                <FormField label='Name' key={'name'}
                    errorText={formErrors?.rdsConfig?.dbName}
                    description={RdsInstanceConfig.shape.dbName.description}>
                    <Input value={item.dbName} inputMode='text'
                        onBlur={() => touchFields(['rdsConfig.dbName'])}
                        onChange={({ detail }) => setFields({ 'rdsConfig.dbName': detail.value })}
                        placeholder='postgres' disabled={isEdit} />
                </FormField>
                <FormField label='Port' key={'port'}
                    errorText={formErrors?.rdsConfig?.dbPort}
                    description={RdsInstanceConfig.shape.dbPort.description}>
                    <Input value={item.dbPort?.toString()}
                        type='number' inputMode='numeric'
                        onBlur={() => touchFields(['rdsConfig.dbPort'])}
                        onChange={({ detail }) => setFields({ 'rdsConfig.dbPort': Number(detail.value) })}
                        disabled={isEdit} />
                </FormField>
            </SpaceBetween>
        </Container>
    );
}
