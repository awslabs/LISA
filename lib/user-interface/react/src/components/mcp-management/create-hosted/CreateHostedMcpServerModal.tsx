/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { ChangeEvent, ReactElement, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    FormField,
    Input,
    Modal,
    Select,
    SelectProps,
    SpaceBetween,
    Textarea,
    TokenGroup,
    Wizard,
} from '@cloudscape-design/components';
import { KeyCode } from '@cloudscape-design/component-toolkit/internal';
import { useAppDispatch } from '@/config/store';
import {
    HostedMcpServerRequest,
    useCreateHostedMcpServerMutation,
} from '@/shared/reducers/mcp-server.reducer';
import { useNotificationService } from '@/shared/util/hooks';
import { EnvironmentVariables } from '@/shared/form/environment-variables';
import { ModifyMethod } from '@/shared/validation/modify-method';

const SERVER_TYPE_OPTIONS: SelectProps.Option[] = [
    { label: 'STDIO', value: 'stdio' },
    { label: 'HTTP', value: 'http' },
    { label: 'SSE', value: 'sse' },
];

type KeyValue = { key: string; value: string };

type FormState = {
    name: string;
    description: string;
    startCommand: string;
    serverType: SelectProps.Option;
    port: string;
    cpu: string;
    memoryLimitMiB: string;
    minCapacity: string;
    maxCapacity: string;
    targetValue: string;
    metricName: string;
    duration: string;
    cooldown: string;
    s3Path: string;
    image: string;
    taskExecutionRoleArn: string;
    taskRoleArn: string;
    groups: string[];
    environment: KeyValue[];
    healthCheckCommand: string;
    healthCheckInterval: string;
    healthCheckTimeout: string;
    healthCheckRetries: string;
    healthCheckStartPeriod: string;
    lbPath: string;
    lbInterval: string;
    lbTimeout: string;
    lbHealthyThreshold: string;
    lbUnhealthyThreshold: string;
};

const INITIAL_FORM_STATE: FormState = {
    name: '',
    description: '',
    startCommand: '',
    serverType: SERVER_TYPE_OPTIONS[0],
    port: '',
    cpu: '256',
    memoryLimitMiB: '512',
    minCapacity: '1',
    maxCapacity: '1',
    targetValue: '10',
    metricName: 'RequestCountPerTarget',
    duration: '60',
    cooldown: '60',
    s3Path: '',
    image: '',
    taskExecutionRoleArn: '',
    taskRoleArn: '',
    groups: [],
    environment: [],
    healthCheckCommand: 'CMD-SHELL curl --fail http://localhost:{{PORT}}/status || exit 1',
    healthCheckInterval: '30',
    healthCheckTimeout: '10',
    healthCheckRetries: '3',
    healthCheckStartPeriod: '0',
    lbPath: '/status',
    lbInterval: '30',
    lbTimeout: '5',
    lbHealthyThreshold: '3',
    lbUnhealthyThreshold: '3',
};

type CreateHostedMcpServerModalProps = {
    visible: boolean;
    setVisible: (visible: boolean) => void;
};

export function CreateHostedMcpServerModal ({ visible, setVisible }: CreateHostedMcpServerModalProps): ReactElement {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const [formState, setFormState] = useState<FormState>(INITIAL_FORM_STATE);
    const [errors, setErrors] = useState<string[]>([]);
    const [activeStepIndex, setActiveStepIndex] = useState(0);
    const [groupInput, setGroupInput] = useState('');

    const [
        createHostedMcpServer,
        { isLoading: isSaving, isSuccess, isError, error: createError }
    ] = useCreateHostedMcpServerMutation();

    useEffect(() => {
        if (!visible) {
            setFormState(INITIAL_FORM_STATE);
            setErrors([]);
            setActiveStepIndex(0);
            setGroupInput('');
        }
    }, [visible]);

    useEffect(() => {
        if (!isSaving && isSuccess) {
            notificationService.generateNotification('Successfully created hosted MCP server', 'success');
            setVisible(false);
        } else if (!isSaving && isError) {
            const message = createError && 'data' in createError
                ? createError.data?.message ?? createError.data
                : 'Unknown error creating hosted MCP server';
            notificationService.generateNotification(`Failed to create hosted MCP server: ${message}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isSaving, isSuccess, isError, createError]);

    const onChange = (field: keyof FormState) => (event: ChangeEvent<HTMLInputElement> | { detail: { value: string } }) => {
        const value = 'detail' in event ? event.detail.value : event.target.value;
        setFormState((previous) => ({
            ...previous,
            [field]: value,
        }));
    };

    const setEnvironmentFields = (values: Record<string, any>, method?: ModifyMethod) => {
        setFormState((prev) => {
            if (method === ModifyMethod.Unset) {
                const key = Object.keys(values)[0];
                const match = key.match(/environment\[(\d+)\]/);
                if (match) {
                    const index = Number(match[1]);
                    return {
                        ...prev,
                        environment: prev.environment.filter((_, i) => i !== index)
                    };
                }
                return prev;
            }

            if (values.environment) {
                return {
                    ...prev,
                    environment: values.environment,
                };
            }

            const key = Object.keys(values)[0];
            const match = key.match(/environment\[(\d+)\]/);
            if (match) {
                const index = Number(match[1]);
                const updated = [...prev.environment];
                const existing = updated[index] ?? { key: '', value: '' };
                updated[index] = { ...existing, ...values[key] };
                return {
                    ...prev,
                    environment: updated,
                };
            }

            return prev;
        });
    };

    const environmentObject = useMemo(() => {
        if (!formState.environment.length) {
            return undefined;
        }
        return formState.environment.reduce((acc, { key, value }) => {
            if (key?.trim()) {
                acc[key.trim()] = value;
            }
            return acc;
        }, {} as Record<string, string>);
    }, [formState.environment]);

    const tokens = useMemo(() => {
        return formState.groups.map((group) => ({
            label: group,
            dismissLabel: `Remove ${group}`,
        }));
    }, [formState.groups]);

    const handleAddGroup = () => {
        const value = groupInput.trim();
        if (!value || formState.groups.includes(value)) {
            return;
        }
        setFormState((prev) => ({
            ...prev,
            groups: [...prev.groups, value],
        }));
        setGroupInput('');
    };

    const handleRemoveGroup = (index: number) => {
        setFormState((prev) => ({
            ...prev,
            groups: prev.groups.filter((_, i) => i !== index),
        }));
    };

    const toNumberOrDefault = (value: string, fallback: number): number => {
        if (value.trim() === '') {
            return fallback;
        }
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };

    const normalizeHealthCheckCommand = (rawCommand: string): string | string[] => {
        const trimmed = rawCommand.trim();
        if (!trimmed) {
            return trimmed;
        }
        const prefixRegex = /^cmd-shell\b/i;
        if (prefixRegex.test(trimmed)) {
            const remainder = trimmed.replace(prefixRegex, '').trim();
            return remainder ? ['CMD-SHELL', remainder] : ['CMD-SHELL'];
        }
        return trimmed;
    };

    const validateStep = (stepIndex: number): string[] => {
        const stepErrors: string[] = [];
        switch (stepIndex) {
            case 0: {
                if (!formState.name.trim()) {
                    stepErrors.push('Name is required.');
                }
                if (!formState.startCommand.trim()) {
                    stepErrors.push('Start command is required.');
                }
                break;
            }
            case 1: {
                const min = Number(formState.minCapacity);
                const max = Number(formState.maxCapacity);
                if (Number.isNaN(min) || min < 1) {
                    stepErrors.push('Minimum capacity must be a positive number.');
                }
                if (Number.isNaN(max) || max < 1) {
                    stepErrors.push('Maximum capacity must be a positive number.');
                }
                if (!Number.isNaN(min) && !Number.isNaN(max) && min > max) {
                    stepErrors.push('Maximum capacity must be greater than or equal to minimum capacity.');
                }
                break;
            }
            case 3: {
                if (!formState.healthCheckCommand.trim()) {
                    stepErrors.push('Container health check command is required.');
                }
                const containerNumericFields = [
                    { value: formState.healthCheckInterval, label: 'Container health check interval' },
                    { value: formState.healthCheckTimeout, label: 'Container health check timeout' },
                    { value: formState.healthCheckRetries, label: 'Container health check retries' },
                    { value: formState.healthCheckStartPeriod, label: 'Container health check start period' },
                ];
                containerNumericFields.forEach(({ value, label }) => {
                    if (value.trim() === '') {
                        stepErrors.push(`${label} is required.`);
                    } else if (Number.isNaN(Number(value))) {
                        stepErrors.push(`${label} must be a number.`);
                    }
                });

                if (!formState.lbPath.trim()) {
                    stepErrors.push('Load balancer health check path is required.');
                }
                const loadBalancerNumericFields = [
                    { value: formState.lbInterval, label: 'Load balancer health check interval' },
                    { value: formState.lbTimeout, label: 'Load balancer health check timeout' },
                    { value: formState.lbHealthyThreshold, label: 'Load balancer healthy threshold' },
                    { value: formState.lbUnhealthyThreshold, label: 'Load balancer unhealthy threshold' },
                ];
                loadBalancerNumericFields.forEach(({ value, label }) => {
                    if (value.trim() === '') {
                        stepErrors.push(`${label} is required.`);
                    } else if (Number.isNaN(Number(value))) {
                        stepErrors.push(`${label} must be a number.`);
                    }
                });
                break;
            }
            default:
                break;
        }
        return stepErrors;
    };

    const handleSubmit = async () => {
        const stepsToValidate = [0, 1, 3];
        const validationErrors = stepsToValidate.flatMap((step) => validateStep(step));
        if (validationErrors.length > 0) {
            setErrors(validationErrors);
            if (validationErrors.some((error) => error.includes('Name') || error.includes('Start command'))) {
                setActiveStepIndex(0);
            } else if (validationErrors.some((error) => error.includes('capacity'))) {
                setActiveStepIndex(1);
            } else if (validationErrors.some((error) => error.toLowerCase().includes('health'))) {
                setActiveStepIndex(3);
            }
            return;
        }

        const trimmedGroups = formState.groups.map((group) => group.trim()).filter(Boolean);
        const groups = trimmedGroups.length > 0 ? trimmedGroups : undefined;

        const portNumber = Number(formState.port);
        const resolvedPort = Number.isFinite(portNumber) && portNumber > 0
            ? portNumber
            : (formState.serverType.value === 'http' || formState.serverType.value === 'sse' ? 8000 : 8080);
        const commandTemplate = formState.healthCheckCommand.trim() || INITIAL_FORM_STATE.healthCheckCommand;
        const command = commandTemplate.replace(/\{\{PORT\}\}/g, `${resolvedPort}`);
        const containerHealthCheckConfig = {
            command: normalizeHealthCheckCommand(command),
            interval: toNumberOrDefault(formState.healthCheckInterval, Number(INITIAL_FORM_STATE.healthCheckInterval)),
            timeout: toNumberOrDefault(formState.healthCheckTimeout, Number(INITIAL_FORM_STATE.healthCheckTimeout)),
            retries: toNumberOrDefault(formState.healthCheckRetries, Number(INITIAL_FORM_STATE.healthCheckRetries)),
            startPeriod: toNumberOrDefault(formState.healthCheckStartPeriod, Number(INITIAL_FORM_STATE.healthCheckStartPeriod)),
        };

        const loadBalancerConfig = {
            healthCheckConfig: {
                path: formState.lbPath.trim() || INITIAL_FORM_STATE.lbPath,
                interval: toNumberOrDefault(formState.lbInterval, Number(INITIAL_FORM_STATE.lbInterval)),
                timeout: toNumberOrDefault(formState.lbTimeout, Number(INITIAL_FORM_STATE.lbTimeout)),
                healthyThresholdCount: toNumberOrDefault(formState.lbHealthyThreshold, Number(INITIAL_FORM_STATE.lbHealthyThreshold)),
                unhealthyThresholdCount: toNumberOrDefault(formState.lbUnhealthyThreshold, Number(INITIAL_FORM_STATE.lbUnhealthyThreshold)),
            }
        };

        const payload: HostedMcpServerRequest = {
            name: formState.name.trim(),
            description: formState.description?.trim() || undefined,
            startCommand: formState.startCommand.trim(),
            serverType: (formState.serverType.value as HostedMcpServerRequest['serverType']) ?? 'stdio',
            port: formState.port ? Number(formState.port) : undefined,
            cpu: formState.cpu ? Number(formState.cpu) : undefined,
            memoryLimitMiB: formState.memoryLimitMiB ? Number(formState.memoryLimitMiB) : undefined,
            autoScalingConfig: {
                minCapacity: Number(formState.minCapacity),
                maxCapacity: Number(formState.maxCapacity),
                targetValue: formState.targetValue ? Number(formState.targetValue) : undefined,
                metricName: formState.metricName || undefined,
                duration: formState.duration ? Number(formState.duration) : undefined,
                cooldown: formState.cooldown ? Number(formState.cooldown) : undefined,
            },
            s3Path: formState.s3Path || undefined,
            image: formState.image || undefined,
            taskExecutionRoleArn: formState.taskExecutionRoleArn || undefined,
            taskRoleArn: formState.taskRoleArn || undefined,
            groups,
            environment: environmentObject,
            containerHealthCheckConfig,
            loadBalancerConfig,
        };

        try {
            await createHostedMcpServer(payload).unwrap();
        } catch {
            // errors surfaced via RTK query state
        }
    };

    const steps = [
        {
            title: 'Server details',
            description: 'Configure name, type, and start command for your hosted MCP server.',
            content: (
                <SpaceBetween size='m'>
                    <FormField label='Name' info='Unique identifier for the hosted MCP server.'>
                        <Input value={formState.name} onChange={onChange('name')} />
                    </FormField>
                    <FormField label='Description'>
                        <Textarea value={formState.description} rows={3} onChange={onChange('description')} />
                    </FormField>
                    <FormField label='Server type'>
                        <Select
                            selectedOption={formState.serverType}
                            onChange={({ detail }) => setFormState((prev) => ({
                                ...prev,
                                serverType: detail.selectedOption,
                            }))}
                            options={SERVER_TYPE_OPTIONS}
                        />
                    </FormField>
                    <FormField label='Base image' info='Optional. Pre-built image or base image URI.'>
                        <Input value={formState.image} onChange={onChange('image')} placeholder='public.ecr.aws/... or registry/image:tag' />
                    </FormField>
                    <FormField
                        label='Start command'
                        info='Command executed when the container starts. For STDIO servers include the binary or script to launch.'
                    >
                        <Textarea value={formState.startCommand} rows={4} onChange={onChange('startCommand')} />
                    </FormField>
                    <FormField
                        label='Container port'
                        info='Optional. Defaults to 8000 for HTTP/SSE or 8080 for STDIO proxy.'
                    >
                        <Input value={formState.port} onChange={onChange('port')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField
                        label='Groups'
                        description='Optional. Restrict access to specific groups. Enter a group name and press return to add it.'
                    >
                        <SpaceBetween size='xs'>
                            <Input
                                value={groupInput}
                                onChange={({ detail }) => setGroupInput(detail.value)}
                                onKeyDown={(event) => {
                                    if (event.detail.keyCode === KeyCode.enter) {
                                        handleAddGroup();
                                        event.preventDefault();
                                    }
                                }}
                                placeholder='Enter group name'
                            />
                            {tokens.length > 0 && (
                                <TokenGroup
                                    items={tokens}
                                    onDismiss={({ detail }) => handleRemoveGroup(detail.itemIndex)}
                                />
                            )}
                        </SpaceBetween>
                    </FormField>
                </SpaceBetween>
            ),
        },
        {
            title: 'Scaling configuration',
            description: 'Define auto scaling parameters and optional metrics for the server.',
            content: (
                <SpaceBetween size='m'>
                    <FormField label='Minimum capacity'>
                        <Input value={formState.minCapacity} onChange={onChange('minCapacity')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Maximum capacity'>
                        <Input value={formState.maxCapacity} onChange={onChange('maxCapacity')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Target value' info='Optional. Target metric value for scaling.'>
                        <Input value={formState.targetValue} onChange={onChange('targetValue')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Metric name' info='Optional. CloudWatch metric for scaling (e.g. RequestCount).'>
                        <Input value={formState.metricName} onChange={onChange('metricName')} />
                    </FormField>
                    <FormField label='Scale duration (seconds)' info='Optional. Period length for the CloudWatch metric.'>
                        <Input value={formState.duration} onChange={onChange('duration')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Cooldown (seconds)' info='Optional. Cooldown between scaling events.'>
                        <Input value={formState.cooldown} onChange={onChange('cooldown')} inputMode='numeric' type='number' />
                    </FormField>
                </SpaceBetween>
            ),
        },
        {
            title: 'Advanced options',
            description: 'Optional image, IAM roles, environment variables.',
            isOptional: true,
            content: (
                <SpaceBetween size='m'>
                    <FormField label='S3 artifact path' info='Optional. S3 URI for server artifacts.'>
                        <Input value={formState.s3Path} onChange={onChange('s3Path')} placeholder='s3://bucket/path' />
                    </FormField>
                    <FormField label='CPU (units)' info='Optional. Defaults to 256 units (0.25 vCPU).'>
                        <Input value={formState.cpu} onChange={onChange('cpu')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Memory (MiB)' info='Optional. Defaults to 512 MiB.'>
                        <Input value={formState.memoryLimitMiB} onChange={onChange('memoryLimitMiB')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField label='Task execution role ARN' info='Optional IAM role for pulling images / reading S3.'>
                        <Input value={formState.taskExecutionRoleArn} onChange={onChange('taskExecutionRoleArn')} />
                    </FormField>
                    <FormField label='Task role ARN' info='Optional IAM role for the running task.'>
                        <Input value={formState.taskRoleArn} onChange={onChange('taskRoleArn')} />
                    </FormField>
                    <EnvironmentVariables
                        item={{ environment: formState.environment }}
                        setFields={setEnvironmentFields}
                        touchFields={() => undefined}
                        formErrors={undefined}
                        propertyPath={['environment']}
                    />
                </SpaceBetween>
            ),
        },
        {
            title: 'Health checks',
            description: 'Configure container and load balancer health monitoring.',
            isOptional: true,
            content: (
                <SpaceBetween size='l'>
                    <SpaceBetween size='m'>
                        <FormField
                            label='Container health check command'
                            description='Command executed inside the container to verify health. Use {{PORT}} to reference the container port.'
                        >
                            <Input
                                value={formState.healthCheckCommand}
                                onChange={onChange('healthCheckCommand')}
                                placeholder='CMD-SHELL curl --fail http://localhost:{{PORT}}/status || exit 1'
                            />
                        </FormField>
                        <FormField label='Interval (seconds)'>
                            <Input
                                value={formState.healthCheckInterval}
                                onChange={onChange('healthCheckInterval')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Timeout (seconds)'>
                            <Input
                                value={formState.healthCheckTimeout}
                                onChange={onChange('healthCheckTimeout')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Retries'>
                            <Input
                                value={formState.healthCheckRetries}
                                onChange={onChange('healthCheckRetries')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Start period (seconds)'>
                            <Input
                                value={formState.healthCheckStartPeriod}
                                onChange={onChange('healthCheckStartPeriod')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                    </SpaceBetween>
                    <SpaceBetween size='m'>
                        <FormField
                            label='Load balancer health check path'
                            description='Relative path used by the load balancer to determine service health.'
                        >
                            <Input
                                value={formState.lbPath}
                                onChange={onChange('lbPath')}
                                placeholder='/status'
                            />
                        </FormField>
                        <FormField label='Interval (seconds)'>
                            <Input
                                value={formState.lbInterval}
                                onChange={onChange('lbInterval')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Timeout (seconds)'>
                            <Input
                                value={formState.lbTimeout}
                                onChange={onChange('lbTimeout')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Healthy threshold'>
                            <Input
                                value={formState.lbHealthyThreshold}
                                onChange={onChange('lbHealthyThreshold')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                        <FormField label='Unhealthy threshold'>
                            <Input
                                value={formState.lbUnhealthyThreshold}
                                onChange={onChange('lbUnhealthyThreshold')}
                                inputMode='numeric'
                                type='number'
                            />
                        </FormField>
                    </SpaceBetween>
                </SpaceBetween>
            ),
        },
        {
            title: 'Review & create',
            description: 'Review configuration before provisioning the hosted MCP server.',
            content: (
                <SpaceBetween size='m'>
                    <Box><strong>Name:</strong> {formState.name || '-'}</Box>
                    <Box><strong>Description:</strong> {formState.description || '-'}</Box>
                    <Box><strong>Server type:</strong> {formState.serverType.label}</Box>
                    <Box><strong>Start command:</strong> <div><code>{formState.startCommand || '-'}</code></div></Box>
                    <Box><strong>Container port:</strong> {formState.port || '8000 (default)'}</Box>
                    <Box><strong>CPU (units):</strong> {formState.cpu || '256 (default)'}</Box>
                    <Box><strong>Memory (MiB):</strong> {formState.memoryLimitMiB || '512 (default)'}</Box>
                    <Box><strong>Base image:</strong> {formState.image || '-'}</Box>
                    <Box><strong>S3 artifact path:</strong> {formState.s3Path || '-'}</Box>
                    <Box><strong>Task execution role ARN:</strong> {formState.taskExecutionRoleArn || '-'}</Box>
                    <Box><strong>Task role ARN:</strong> {formState.taskRoleArn || '-'}</Box>
                    <Box><strong>Auto scaling (min / max):</strong> {formState.minCapacity} / {formState.maxCapacity}</Box>
                    <Box><strong>Auto scaling target value:</strong> {formState.targetValue || '-'}</Box>
                    <Box><strong>Auto scaling metric name:</strong> {formState.metricName || '-'}</Box>
                    <Box><strong>Auto scaling duration (seconds):</strong> {formState.duration || '-'}</Box>
                    <Box><strong>Auto scaling cooldown (seconds):</strong> {formState.cooldown || '-'}</Box>
                    <Box><strong>Environment variables:</strong> {formState.environment.length ? formState.environment.map(({ key, value }) => `${key}=${value}`).join(', ') : 'None'}</Box>
                    <Box><strong>Groups:</strong> {formState.groups.length ? formState.groups.join(', ') : '(public)'}</Box>
                    <Box><strong>Container health check command:</strong> {formState.healthCheckCommand}</Box>
                    <Box><strong>Container health check interval / timeout / retries / start period:</strong> {`${formState.healthCheckInterval}s / ${formState.healthCheckTimeout}s / ${formState.healthCheckRetries} / ${formState.healthCheckStartPeriod}s`}</Box>
                    <Box><strong>Load balancer health check path:</strong> {formState.lbPath}</Box>
                    <Box><strong>Load balancer interval / timeout:</strong> {`${formState.lbInterval}s / ${formState.lbTimeout}s`}</Box>
                    <Box><strong>Load balancer healthy / unhealthy thresholds:</strong> {`${formState.lbHealthyThreshold} / ${formState.lbUnhealthyThreshold}`}</Box>
                </SpaceBetween>
            ),
        },
    ];

    return (
        <Modal
            visible={visible}
            onDismiss={() => setVisible(false)}
            header='Create hosted MCP server'
            size='large'
        >
            <SpaceBetween size='m'>
                {errors.length > 0 && (
                    <Alert type='error' header='Please address the following issues'>
                        <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                            {errors.map((error) => (
                                <li key={error}>{error}</li>
                            ))}
                        </ul>
                    </Alert>
                )}
                <Wizard
                    steps={steps}
                    activeStepIndex={activeStepIndex}
                    submitButtonText='Create server'
                    isLoadingNextStep={isSaving}
                    i18nStrings={{
                        stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                        collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                        cancelButton: 'Cancel',
                        previousButton: 'Previous',
                        nextButton: 'Next',
                        optional: 'Optional',
                    }}
                    onNavigate={({ detail }) => {
                        const { reason, requestedStepIndex } = detail;
                        if (reason === 'next') {
                            const currentErrors = validateStep(activeStepIndex);
                            if (currentErrors.length > 0) {
                                setErrors(currentErrors);
                                return;
                            }
                            setErrors([]);
                        } else if (reason === 'previous' || reason === 'step') {
                            setErrors([]);
                        }
                        setActiveStepIndex(requestedStepIndex);
                    }}
                    onCancel={() => setVisible(false)}
                    onSubmit={() => handleSubmit()}
                />
            </SpaceBetween>
        </Modal>
    );
}

export default CreateHostedMcpServerModal;

