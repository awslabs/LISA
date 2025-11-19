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

import _ from 'lodash';
import React, { ReactElement, useEffect, useMemo } from 'react';
import ActivatedUserComponents from './ActivatedUserComponents';
import SystemBannerConfiguration from './SystemBannerConfiguration';
import { scrollToInvalid, useValidationReducer } from '../../shared/validation';
import { IConfiguration, SystemConfiguration, SystemConfigurationSchema } from '../../shared/model/configuration.model';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { Button, Header } from '@cloudscape-design/components';
import { useGetConfigurationQuery, useUpdateConfigurationMutation } from '../../shared/reducers/configuration.reducer';
import { useAppDispatch, useAppSelector } from '../../config/store';
import { selectCurrentUsername } from '../../shared/reducers/user.reducer';
import { getJsonDifference } from '../../shared/util/validationUtils';
import { setConfirmationModal } from '../../shared/reducers/modal.reducer';
import { useNotificationService } from '../../shared/util/hooks';
import { mcpServerApi } from '@/shared/reducers/mcp-server.reducer';

export type ConfigState = {
    validateAll: boolean;
    form: SystemConfiguration;
    touched: any;
    formSubmitting: boolean;
};

export function ConfigurationComponent(): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const {
        data: config,
        isFetching: isFetchingConfig,
    } = useGetConfigurationQuery('global', { refetchOnMountOrArgChange: true });
    const [
        updateConfigMutation,
        {
            isSuccess: isUpdateSuccess,
            isError: isUpdateError,
            error: updateError,
            isLoading: isUpdating,
            reset: resetUpdate,
        },
    ] = useUpdateConfigurationMutation();
    const initialForm = SystemConfigurationSchema.parse({});
    const currentUsername = useAppSelector(selectCurrentUsername);
    const {
        state,
        setState,
        setFields,
        touchFields,
        errors,
        isValid,
    } = useValidationReducer(SystemConfigurationSchema, {
        validateAll: false as boolean,
        touched: {},
        formSubmitting: false as boolean,
        form: {
            ...initialForm,
        },
    } as ConfigState);

    /**
     * Converts a JSON object into an outline structure represented as React nodes.
     *
     * @param {object} [json={}] - The JSON object to be converted.
     * @returns {React.ReactNode[]} - An array of React nodes representing the outline structure.
     */
    function jsonToOutline(json = {}) {
        const output: React.ReactNode[] = [];

        for (const key in json) {
            const value = json[key];
            output.push((
                <li key={key}><p><strong>{_.startCase(key)}</strong>{_.isPlainObject(value) ? '' : `: ${value}`}</p>
                </li>));

            if (_.isPlainObject(value)) {
                const recursiveJson = jsonToOutline(value); // recursively call
                output.push((recursiveJson));
            }
        }
        return <ul>{output}</ul>;
    }

    const changesDiff = useMemo(() => {
        return getJsonDifference(config && config[0] ? config[0].configuration : initialForm, state.form);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialForm, state.form]);

    useEffect(() => {
        if (!isFetchingConfig && config != null) {
            setState({
                ...state,
                form: {
                    ...config[0]?.configuration,
                },
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [config, isFetchingConfig]);

    useEffect(() => {
        if (!isUpdating && isUpdateSuccess) {
            notificationService.generateNotification('Successfully updated configuration', 'success');

            // invalidate the mcp servers on update in case they've changed
            dispatch(mcpServerApi.util.invalidateTags(['mcpServers']));

            resetUpdate();
        } else if (!isUpdating && isUpdateError) {
            notificationService.generateNotification(`Error updating config: ${updateError.data?.message ?? updateError.data}`, 'error');
            resetUpdate();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSuccess, isUpdating, isUpdateError, updateError]);

    function handleSubmit() {
        if (isValid && !_.isEmpty(changesDiff)) {
            const toSubmit: IConfiguration = {
                configuration: state.form,
                configScope: 'global',
                versionId: Number(config[0]?.versionId) + 1,
                changedBy: currentUsername ?? 'Admin',
                changeReason: `Changes to: ${Object.keys(changesDiff)}`,
            };
            dispatch(
                setConfirmationModal({
                    action: 'Update',
                    resourceName: 'Configuration',
                    onConfirm: () => updateConfigMutation(toSubmit),
                    description: _.isEmpty(changesDiff) ? <p>No changes detected</p> : jsonToOutline(changesDiff),
                }));
        }
    }

    return (
        <SpaceBetween size={'m'}>
            <Header
                variant='h1'
                description={'Activate and deactivate platform features'}
            >
                LISA Feature Configuration
            </Header>
            <ActivatedUserComponents setFields={setFields} enabledComponents={state.form.enabledComponents} />
            <SystemBannerConfiguration setFields={setFields}
                textColor={state.form.systemBanner.textColor}
                backgroundColor={state.form.systemBanner.backgroundColor}
                text={state.form.systemBanner.text}
                isEnabled={state.form.systemBanner.isEnabled}
                touchFields={touchFields}
                errors={errors} />
            <SpaceBetween alignItems='end' direction='vertical' size={'s'}>
                <Button
                    iconAlt='Update configuration'
                    variant='primary'
                    onClick={() => {
                        if (!isValid) {
                            setState({ validateAll: true, formSubmitting: false });
                            scrollToInvalid();
                        } else {
                            handleSubmit();
                        }
                    }}
                    loading={isUpdating}
                    data-cy='configuration-submit'
                    disabled={isUpdating || _.isEmpty(changesDiff)}
                >
                    Save Changes
                </Button>
            </SpaceBetween>
        </SpaceBetween>
    );
}

export default ConfigurationComponent;
