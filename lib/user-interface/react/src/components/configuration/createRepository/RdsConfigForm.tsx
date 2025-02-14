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
import { Header } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import React, { ReactElement } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import { RdsConfig as RdsConfigSchema } from '../../../../../../configSchema';

type RdsConfigProps = {
    isEdit: boolean
};

export function RdsConfigForm (props: FormProps<RdsConfigSchema> & RdsConfigProps): ReactElement {
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    return (
        <Container header={<Header variant='h2'>RDS Config</Header>}>
            <FormField label='Username' errorText={formErrors?.rdsConfig?.username}>
                <Input value={item.username} inputMode='text'
                       onBlur={() => touchFields(['rdsConfig.username'])}
                       onChange={({ detail }) => setFields({ 'rdsConfig.username': detail.value })}
                       placeholder="RDS Username" disabled={isEdit} />
            </FormField>
            <FormField label='Password Secret Id (optional)'
                       errorText={formErrors?.rdsConfig?.passwordSecretId}>
                <Input value={item.passwordSecretId} inputMode='text'
                       onBlur={() => touchFields(['rdsConfig.passwordSecretId'])}
                       onChange={({ detail }) => setFields({ 'rdsConfig.passwordSecretId': detail.value })}
                       placeholder="RDS Password Secret Id" disabled={isEdit} />
            </FormField>
            <FormField label='DB Host (optional)'
                       errorText={formErrors?.rdsConfig?.dbHost}>
                <Input value={item.dbHost} inputMode='text'
                       onBlur={() => touchFields(['rdsConfig.dbHost'])}
                       onChange={({ detail }) => setFields({ 'rdsConfig.dbHost': detail.value })}
                       placeholder="DB Host" disabled={isEdit} />
            </FormField>
            <FormField label='DB Name'
                       errorText={formErrors?.rdsConfig?.dbName}>
                <Input value={item.dbName} inputMode='text'
                       onBlur={() => touchFields(['rdsConfig.dbName'])}
                       onChange={({ detail }) => setFields({ 'rdsConfig.dbName': detail.value })}
                       placeholder="DB Name" disabled={isEdit} />
            </FormField>
            <FormField label='DB Port'
                       errorText={formErrors?.rdsConfig?.dbPort}>
                <Input value={item.dbPort?.toString()}
                       type="number" inputMode="numeric"
                       onBlur={() => touchFields(['rdsConfig.dbPort'])}
                       onChange={({ detail }) => setFields({ 'rdsConfig.dbPort': Number(detail.value) })}
                       disabled={isEdit} />
            </FormField>
        </Container>
    );
}
