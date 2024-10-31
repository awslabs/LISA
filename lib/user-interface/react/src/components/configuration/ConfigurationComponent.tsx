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
import ActivatedUserComponents from './ActivatedUserComponents';
import SystemBannerConfiguration from './SystemBannerConfiguration';
import { scrollToInvalid, useValidationReducer } from '../../shared/validation';
import { SystemConfiguration, SystemConfigurationSchema } from '../../shared/model/configuration.model';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { Button, Header } from '@cloudscape-design/components';
import { ModelStatus, ModelType } from '../../shared/model/model-management.model';
import { useGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';

export type ConfigState = {
    validateAll: boolean;
    form: SystemConfiguration;
    touched: any;
    formSubmitting: boolean;
    activeStepIndex: number;
};

export function ConfigurationComponent () : ReactElement {
    const { data: config, isFetching: isFetchingConfig } = useGetConfigurationQuery("global", {refetchOnMountOrArgChange: 5,
        selectFromResult: (state) => ({
            isFetching: state.isFetching,
            data: (state.data || []).filter((model) => model.modelType === ModelType.textgen && model.status === ModelStatus.InService),
        })});
    const initialForm = SystemConfigurationSchema.parse({});
    const { state, setState, setFields, touchFields, errors, isValid } = useValidationReducer(SystemConfigurationSchema, {
        validateAll: false as boolean,
        touched: {},
        formSubmitting: false as boolean,
        form: {
            ...initialForm
        },
        activeStepIndex: 0,
    } as ConfigState);

    return (
        <SpaceBetween size={'m'}>
            <Header
                variant='h1'
                description={`The current configuration of LISA`}
            >
                LISA App Configuration
            </Header>
            <ActivatedUserComponents setFields={setFields} enabledComponents={state.form.enabledComponents} />
            <SystemBannerConfiguration setFields={setFields}
                                       textColor={state.form.systemBanner.textColor}
                                       backgroundColor={state.form.systemBanner.backgroundColor}
                                       text={state.form.systemBanner.text}
                                       isEnabled={state.form.systemBanner.isEnabled}
                                       touchFields={touchFields}
                                       errors={errors}/>
            <SpaceBetween alignItems='end' direction='vertical' size={'s'}>
                <Button
                    iconAlt='Update dynamic configuration'
                    variant='primary'
                    onClick={() => {
                        if (!isValid) {
                            setState({ validateAll: true, formSubmitting: false });
                            scrollToInvalid();
                        } else {
                            // setModalVisible(true);
                        }
                    }}
                    loading={state.formSubmitting}
                    data-cy='dynamic-configuration-submit'
                    disabled={state.formSubmitting}
                >
                    Save Changes
                </Button>
            </SpaceBetween>

        </SpaceBetween>
    );
}

export default ConfigurationComponent;
