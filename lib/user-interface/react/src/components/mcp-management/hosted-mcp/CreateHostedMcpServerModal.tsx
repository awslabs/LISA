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
import { ReactElement, useEffect, useMemo } from 'react';
import { Box, ExpandableSection, Header, Modal, SpaceBetween, Wizard } from '@cloudscape-design/components';
import { useAppDispatch } from '@/config/store';
import {
    HostedMcpServer,
    HostedMcpServerRequestSchema,
    HostedMcpServerRequestForm,
} from '@/shared/model/hosted-mcp-server.model';
import {
    useCreateHostedMcpServerMutation,
    useUpdateHostedMcpServerMutation,
} from '@/shared/reducers/mcp-server.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { useValidationReducer } from '@/shared/validation';
import { ModifyMethod } from '@/shared/validation/modify-method';
import { getJsonDifference } from '@/shared/util/validationUtils';
import { getDefaults } from '#root/lib/schema/zodUtil';
import { ServerDetailsConfig } from './ServerDetailsConfig';
import { ScalingConfig } from './ScalingConfig';
import { AdvancedOptionsConfig } from './AdvancedOptionsConfig';
import { HealthChecksConfig } from './HealthChecksConfig';
import { formToPayload } from './formHelpers';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';

type CreateHostedMcpServerModalProps = {
    visible: boolean;
    setVisible: (visible: boolean) => void;
    isEdit: boolean;
    selectedServer?: HostedMcpServer | null;
};

export function CreateHostedMcpServerModal ({
    visible,
    setVisible,
    isEdit,
    selectedServer,
}: CreateHostedMcpServerModalProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const [createHostedMcpServer, { isLoading: isCreating, isSuccess: isCreateSuccess, isError: isCreateError, error: createError }] =
        useCreateHostedMcpServerMutation();

    const [updateHostedMcpServer, { isLoading: isUpdating, isSuccess: isUpdateSuccess, isError: isUpdateError, error: updateError }] =
        useUpdateHostedMcpServerMutation();

    const isSaving = isCreating || isUpdating;
    const isSuccess = isCreateSuccess || isUpdateSuccess;
    const isError = isCreateError || isUpdateError;

    // Get default form values
    const initialForm: HostedMcpServerRequestForm = useMemo(() => {
        return getDefaults(HostedMcpServerRequestSchema);
    }, []);

    const { state, setState, setFields, touchFields, errors, isValid } = useValidationReducer(
        HostedMcpServerRequestSchema,
        {
            validateAll: false,
            touched: {},
            formSubmitting: false,
            form: initialForm,
            activeStepIndex: 0,
        }
    );

    // Initialize form data when modal opens
    useEffect(() => {
        if (visible) {
            if (isEdit && selectedServer) {
                // Convert server data to form format
                const healthCheckCommand = Array.isArray(selectedServer.containerHealthCheckConfig?.command)
                    ? selectedServer.containerHealthCheckConfig.command.join(' ')
                    : selectedServer.containerHealthCheckConfig?.command;

                const formData: HostedMcpServerRequestForm = {
                    ...initialForm,
                    name: selectedServer.name,
                    description: selectedServer.description || '',
                    startCommand: selectedServer.startCommand,
                    serverType: selectedServer.serverType,
                    port: selectedServer.port,
                    cpu: selectedServer.cpu || 256,
                    memoryLimitMiB: selectedServer.memoryLimitMiB || 512,
                    autoScalingConfig: {
                        minCapacity: selectedServer.autoScalingConfig?.minCapacity ?? initialForm.autoScalingConfig.minCapacity,
                        maxCapacity: selectedServer.autoScalingConfig?.maxCapacity ?? initialForm.autoScalingConfig.maxCapacity,
                        targetValue: selectedServer.autoScalingConfig?.targetValue ?? initialForm.autoScalingConfig.targetValue,
                        metricName: selectedServer.autoScalingConfig?.metricName ?? initialForm.autoScalingConfig.metricName,
                        duration: selectedServer.autoScalingConfig?.duration ?? initialForm.autoScalingConfig.duration,
                        cooldown: selectedServer.autoScalingConfig?.cooldown ?? initialForm.autoScalingConfig.cooldown,
                    },
                    containerHealthCheckConfig: selectedServer.containerHealthCheckConfig
                        ? {
                            command: healthCheckCommand || initialForm.containerHealthCheckConfig?.command || '',
                            interval: selectedServer.containerHealthCheckConfig.interval ?? initialForm.containerHealthCheckConfig?.interval ?? 30,
                            timeout: selectedServer.containerHealthCheckConfig.timeout ?? initialForm.containerHealthCheckConfig?.timeout ?? 10,
                            retries: selectedServer.containerHealthCheckConfig.retries ?? initialForm.containerHealthCheckConfig?.retries ?? 3,
                            startPeriod: selectedServer.containerHealthCheckConfig.startPeriod ?? initialForm.containerHealthCheckConfig?.startPeriod ?? 180,
                        }
                        : initialForm.containerHealthCheckConfig,
                    loadBalancerConfig: selectedServer.loadBalancerConfig
                        ? {
                            healthCheckConfig: {
                                path: selectedServer.loadBalancerConfig.healthCheckConfig?.path ?? initialForm.loadBalancerConfig?.healthCheckConfig.path ?? '/status',
                                interval: selectedServer.loadBalancerConfig.healthCheckConfig?.interval ?? initialForm.loadBalancerConfig?.healthCheckConfig.interval ?? 30,
                                timeout: selectedServer.loadBalancerConfig.healthCheckConfig?.timeout ?? initialForm.loadBalancerConfig?.healthCheckConfig.timeout ?? 5,
                                healthyThresholdCount: selectedServer.loadBalancerConfig.healthCheckConfig?.healthyThresholdCount ?? initialForm.loadBalancerConfig?.healthCheckConfig.healthyThresholdCount ?? 3,
                                unhealthyThresholdCount: selectedServer.loadBalancerConfig.healthCheckConfig?.unhealthyThresholdCount ?? initialForm.loadBalancerConfig?.healthCheckConfig.unhealthyThresholdCount ?? 3,
                            }
                        }
                        : initialForm.loadBalancerConfig,
                    groups: selectedServer.groups ?? [],
                    environment: selectedServer.environment
                        ? Object.entries(selectedServer.environment).map(([key, value]) => ({ key, value }))
                        : [],
                    image: selectedServer.image,
                    s3Path: selectedServer.s3Path,
                    taskExecutionRoleArn: selectedServer.taskExecutionRoleArn,
                    taskRoleArn: selectedServer.taskRoleArn,
                };

                setState({
                    form: formData,
                });
            } else if (!isEdit) {
                // For create mode, use defaults
                setState({
                    form: initialForm,
                });
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [visible, isEdit, selectedServer]);

    // Reset form when modal closes
    useEffect(() => {
        if (!visible) {
            setState({
                validateAll: false,
                touched: {},
                formSubmitting: false,
                form: initialForm,
                activeStepIndex: 0,
            }, ModifyMethod.Set);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [visible]);

    // Handle API responses
    useEffect(() => {
        if (!isSaving && isSuccess) {
            const message = isEdit
                ? `Successfully updated hosted MCP server ${selectedServer?.name}`
                : 'Successfully created hosted MCP server';
            notificationService.generateNotification(message, 'success');
            setVisible(false);
        } else if (!isSaving && isError) {
            const error = createError || updateError;
            const action = isEdit ? 'updating' : 'creating';
            const message =
                error && 'data' in error
                    ? error.data?.message ?? error.data
                    : `Unknown error ${action} hosted MCP server`;
            notificationService.generateNotification(
                `Failed to ${action.replace('ing', '')} hosted MCP server: ${message}`,
                'error'
            );
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isSaving, isSuccess, isError, createError, updateError, isEdit]);

    const handleSubmit = async () => {
        // Validate all fields
        setState({ validateAll: true });

        if (!isValid) {
            return;
        }

        try {
            const payload = formToPayload(state.form, isEdit, selectedServer);

            if (isEdit && selectedServer) {
                // Calculate what changed
                const diff = getJsonDifference(selectedServer, payload);

                if (!_.isEmpty(diff)) {
                    // Only send updatable fields, following model management pattern
                    const updateFields: any = _.pick(diff, [
                        'description',
                        'groups',
                        'cpu',
                        'memoryLimitMiB',
                        'autoScalingConfig',
                        'environment',
                        'containerHealthCheckConfig',
                        'loadBalancerConfig',
                    ]);

                    // Build update request - similar to model management approach
                    const updatePayload: any = {};

                    // Pick basic fields that aren't undefined (includes empty arrays/strings)
                    const basicFields = _.pickBy(updateFields, (value, key) =>
                        ['description', 'groups', 'cpu', 'memoryLimitMiB'].includes(key) &&
                        value !== undefined
                    );
                    Object.assign(updatePayload, basicFields);

                    // Handle autoScalingConfig if present
                    if (updateFields.autoScalingConfig !== undefined) {
                        const asgConfig = _.pickBy(updateFields.autoScalingConfig, (v) => v !== undefined);
                        if (Object.keys(asgConfig).length > 0) {
                            updatePayload.autoScalingConfig = asgConfig;
                        }
                    }

                    // Handle complex configs if present
                    if (updateFields.environment !== undefined) {
                        updatePayload.environment = updateFields.environment;
                    }
                    if (updateFields.containerHealthCheckConfig !== undefined) {
                        updatePayload.containerHealthCheckConfig = updateFields.containerHealthCheckConfig;
                    }
                    if (updateFields.loadBalancerConfig !== undefined) {
                        updatePayload.loadBalancerConfig = updateFields.loadBalancerConfig;
                    }

                    await updateHostedMcpServer({ serverId: selectedServer.id, payload: updatePayload }).unwrap();
                }
            } else {
                await createHostedMcpServer(payload).unwrap();
            }
        } catch {
            // Errors handled via RTK query state
        }
    };

    const steps = [
        {
            title: 'MCP server details',
            description: 'Configure name, type, and start command for your new LISA hosted MCP server.',
            content: (
                <ServerDetailsConfig
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit}
                />
            ),
        },
        {
            title: 'Scaling configuration',
            description: 'Define auto scaling parameters and optional metrics for the new ECS Fargate cluster for this MCP server.',
            isOptional: true,
            content: (
                <ScalingConfig
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                />
            ),
        },
        {
            title: 'Advanced options',
            description: 'Optional image, IAM roles, environment variables.',
            isOptional: true,
            content: (
                <AdvancedOptionsConfig
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                    isEdit={isEdit}
                />
            ),
        },
        {
            title: 'Health checks',
            description: 'Configure container and load balancer health monitoring.',
            isOptional: true,
            content: (
                <HealthChecksConfig
                    item={state.form}
                    setFields={setFields}
                    touchFields={touchFields}
                    formErrors={errors}
                />
            ),
        },
        {
            title: isEdit ? 'Review and Update' : 'Review and Create',
            description: 'Review configuration before provisioning the hosted MCP server.',
            content: (
                <SpaceBetween size='l'>
                    <ExpandableSection headerText='Server details' defaultExpanded={true}>
                        <SpaceBetween size='xs'>
                            <Box><strong>Name:</strong> {state.form.name || '-'}</Box>
                            <Box><strong>Description:</strong> {state.form.description || '-'}</Box>
                            <Box><strong>Server type:</strong> {state.form.serverType}</Box>
                            <Box><strong>Base image:</strong> {state.form.image || '-'}</Box>
                            <Box><strong>Start command:</strong> <div><code>{state.form.startCommand || '-'}</code></div></Box>
                            <Box><strong>Container port:</strong> {state.form.port || 'default'}</Box>
                            <Box><strong>Groups:</strong> {state.form.groups?.length ? state.form.groups.join(', ') : '(public)'}</Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Scaling configuration' defaultExpanded={false}>
                        <SpaceBetween size='xs'>
                            <Box><strong>Min capacity:</strong> {state.form.autoScalingConfig.minCapacity}</Box>
                            <Box><strong>Max capacity:</strong> {state.form.autoScalingConfig.maxCapacity}</Box>
                            <Box><strong>Target value:</strong> {state.form.autoScalingConfig.targetValue || '-'}</Box>
                            <Box><strong>Metric name:</strong> {state.form.autoScalingConfig.metricName || '-'}</Box>
                            <Box><strong>Duration:</strong> {state.form.autoScalingConfig.duration ? `${state.form.autoScalingConfig.duration}s` : '-'}</Box>
                            <Box><strong>Cooldown:</strong> {state.form.autoScalingConfig.cooldown ? `${state.form.autoScalingConfig.cooldown}s` : '-'}</Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Advanced options' defaultExpanded={false}>
                        <SpaceBetween size='xs'>
                            <Box><strong>S3 artifact path:</strong> {state.form.s3Path || '-'}</Box>
                            <Box><strong>CPU:</strong> {state.form.cpu ? `${state.form.cpu} units` : '-'}</Box>
                            <Box><strong>Memory:</strong> {state.form.memoryLimitMiB ? `${state.form.memoryLimitMiB} MiB` : '-'}</Box>
                            <Box><strong>Task execution role ARN:</strong> {state.form.taskExecutionRoleArn || '-'}</Box>
                            <Box><strong>Task role ARN:</strong> {state.form.taskRoleArn || '-'}</Box>
                            <Box><strong>Environment variables:</strong>{' '}
                                {state.form.environment?.length
                                    ? state.form.environment.map(({ key, value }) => `${key}=${value}`).join(', ')
                                    : 'None'}
                            </Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Health checks' defaultExpanded={false}>
                        <SpaceBetween size='m'>
                            <div>
                                <Header variant='h3'>Container Health Check</Header>
                                <SpaceBetween size='xs'>
                                    <Box><strong>Command:</strong> {state.form.containerHealthCheckConfig?.command || '-'}</Box>
                                    <Box><strong>Interval:</strong> {state.form.containerHealthCheckConfig?.interval}s</Box>
                                    <Box><strong>Timeout:</strong> {state.form.containerHealthCheckConfig?.timeout}s</Box>
                                    <Box><strong>Retries:</strong> {state.form.containerHealthCheckConfig?.retries}</Box>
                                    <Box><strong>Start period:</strong> {state.form.containerHealthCheckConfig?.startPeriod}s</Box>
                                </SpaceBetween>
                            </div>
                            <div>
                                <Header variant='h3'>Load Balancer Health Check</Header>
                                <SpaceBetween size='xs'>
                                    <Box><strong>Path:</strong> {state.form.loadBalancerConfig?.healthCheckConfig?.path}</Box>
                                    <Box><strong>Interval:</strong> {state.form.loadBalancerConfig?.healthCheckConfig?.interval}s</Box>
                                    <Box><strong>Timeout:</strong> {state.form.loadBalancerConfig?.healthCheckConfig?.timeout}s</Box>
                                    <Box><strong>Healthy threshold:</strong> {state.form.loadBalancerConfig?.healthCheckConfig?.healthyThresholdCount}</Box>
                                    <Box><strong>Unhealthy threshold:</strong> {state.form.loadBalancerConfig?.healthCheckConfig?.unhealthyThresholdCount}</Box>
                                </SpaceBetween>
                            </div>
                        </SpaceBetween>
                    </ExpandableSection>
                </SpaceBetween>
            ),
        },
    ];

    return (
        <Modal
            visible={visible}
            onDismiss={() => {
                dispatch(
                    setConfirmationModal({
                        action: 'Discard',
                        resourceName: 'LISA Hosted MCP Server',
                        onConfirm: () => {
                            setVisible(false);
                        },
                        description: 'Are you sure you want to discard your changes?'
                    }));
            }}
            header={isEdit ? `Update LISA Hosted MCP server: ${selectedServer?.name}` : 'Create LISA Hosted MCP Server'}
            size='large'
        >
            <Wizard
                steps={steps}
                activeStepIndex={state.activeStepIndex}
                submitButtonText={isEdit ? 'Update server' : 'Create server'}
                isLoadingNextStep={isSaving}
                allowSkipTo
                i18nStrings={{
                    stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                    collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                    skipToButtonLabel: () => (isEdit ? 'Skip to Update' : 'Skip to Create'),
                    navigationAriaLabel: 'Steps',
                    cancelButton: 'Cancel',
                    previousButton: 'Previous',
                    nextButton: 'Next',
                    optional: 'Optional',
                }}
                onNavigate={({ detail }) => {
                    setState({ activeStepIndex: detail.requestedStepIndex });
                }}
                onCancel={() => {
                    dispatch(
                        setConfirmationModal({
                            action: 'Discard',
                            resourceName: 'LISA Hosted MCP Server',
                            onConfirm: () => {
                                setVisible(false);
                            },
                            description: 'Are you sure you want to discard your changes?'
                        }));
                }}

                onSubmit={handleSubmit}
            />
        </Modal>
    );
}

export default CreateHostedMcpServerModal;
