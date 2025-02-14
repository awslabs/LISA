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
import { Checkbox, Header } from '@cloudscape-design/components';
import FormField from '@cloudscape-design/components/form-field';
import Tiles from '@cloudscape-design/components/tiles';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import React, { ReactElement, useMemo, useState } from 'react';
import { FormProps } from '../../../shared/form/form-props';
import { OpenSearchConfig } from '../../../../../../configSchema';
import { EbsDeviceVolumeType } from '../../../../../../cdk';
import { useGetInstancesQuery } from '../../../shared/reducers/model-management.reducer';
import SpaceBetween from '@cloudscape-design/components/space-between';

type OpenSearchConfigProps = {
    isEdit: boolean
};

export function OpenSearchConfigForm (props: FormProps<OpenSearchConfig> & OpenSearchConfigProps): ReactElement {
    const [useExistingConfig, setUseExistingConfig] = useState('');
    const { data: instances, isLoading: isLoadingInstances } = useGetInstancesQuery();
    const { item, touchFields, setFields, formErrors, isEdit } = props;

    const instanceOptions = useMemo(() => {
        return instances?.map((instance) => ({ value: `${instance}.search` })) || [];
    }, [instances]);

    return (
        <Container header={<Header variant='h2'>OpenSearch Config</Header>}>
            <SpaceBetween size={'s'}>
                <FormField>
                    <Tiles
                        onChange={({ detail }) => setUseExistingConfig(detail.value)}
                        columns={-1}
                        value={useExistingConfig}
                        items={[
                            { label: 'Create new', value: '' },
                            { label: 'Use existing', value: 'true' },
                        ]}
                        readOnly={isEdit}
                    />
                </FormField>
            </SpaceBetween>
            {useExistingConfig ?
                <FormField label='Endpoint' errorText={formErrors?.opensearchConfig?.endpoint}>
                    <Input
                        value={item.endpoint}
                        inputMode='text'
                        onBlur={() => touchFields(['opensearchConfig.endpoint'])}
                        onChange={({ detail }) => setFields({ 'opensearchConfig.endpoint': detail.value })}
                        disabled={isEdit}
                    />
                </FormField>
                :
                <>
                    <FormField label='Data Nodes' errorText={formErrors?.opensearchConfig?.dataNodes}>
                        <Input value={item.dataNodes?.toString()}
                            type='number' inputMode='numeric'
                            onBlur={() => touchFields(['opensearchConfig.dataNodes'])}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.dataNodes': Number(detail.value) })}
                            disabled={isEdit} />
                    </FormField>
                    <FormField label='Data Node Instance Type'
                        errorText={formErrors?.opensearchConfig?.dataNodeInstanceType}>
                        <Select
                            options={instanceOptions}
                            selectedOption={{ value: item.dataNodeInstanceType }}
                            loadingText='Loading instances'
                            disabled={isEdit}
                            onBlur={() => touchFields(['opensearchConfig.dataNodeInstanceType'])}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.dataNodeInstanceType': detail.selectedOption.value })}
                            filteringType='auto'
                            statusType={isLoadingInstances ? 'loading' : 'finished'}
                            virtualScroll
                        />
                    </FormField>
                    <FormField label='Master Nodes'
                        errorText={formErrors?.opensearchConfig?.masterNodes}>
                        <Input value={item.masterNodes?.toString()}
                            type='number' inputMode='numeric'
                            onBlur={() => touchFields(['opensearchConfig.masterNodes'])}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.masterNodes': Number(detail.value) })}
                            disabled={isEdit} />
                    </FormField>
                    <FormField label='Master Node Instance Type'
                        errorText={formErrors?.opensearchConfig?.masterNodeInstanceType}>
                        <Select
                            options={instanceOptions}
                            selectedOption={{ value: item.masterNodeInstanceType }}
                            loadingText='Loading instances'
                            disabled={isEdit}
                            onBlur={() => touchFields(['opensearchConfig.masterNodeInstanceType'])}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.masterNodeInstanceType': detail.selectedOption.value })}
                            filteringType='auto'
                            statusType={isLoadingInstances ? 'loading' : 'finished'}
                            virtualScroll
                        />
                    </FormField>
                    <FormField label='Volume Size'
                        errorText={formErrors?.opensearchConfig?.volumeSize}>
                        <Input value={item.volumeSize?.toString()}
                            type='number' inputMode='numeric'
                            onBlur={() => touchFields(['opensearchConfig.volumeSize'])}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.volumeSize': Number(detail.value) })}
                            disabled={isEdit} />
                    </FormField>
                    <FormField label='Volume Type'
                        errorText={formErrors?.opensearchConfig?.volumeType}>
                        <Select
                            selectedOption={{
                                label: item.volumeType,
                                value: item.volumeType,
                            }}
                            onChange={({ detail }) => setFields({ 'opensearchConfig.volumeType': detail.selectedOption.value })}
                            onBlur={() => touchFields(['opensearchConfig.volumeType'])}
                            options={Object.keys(EbsDeviceVolumeType).map((key) => ({
                                label: key,
                                value: EbsDeviceVolumeType[key],
                            }),
                            )}
                            disabled={isEdit}
                        />
                    </FormField>
                    <FormField>
                        <Checkbox
                            onChange={({ detail }) => setFields({ 'opensearchConfig.multiAzWithStandby': detail.checked })}
                            checked={item.multiAzWithStandby}
                            disabled={isEdit}>
                            Multiple AZ With Standby
                        </Checkbox>
                    </FormField>
                </>
            }
        </Container>
    );
}
