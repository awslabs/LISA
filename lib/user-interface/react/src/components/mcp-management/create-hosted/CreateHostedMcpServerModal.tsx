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

import { ChangeEvent, ReactElement, useEffect, useMemo, useState } from 'react';
import {
    Box,
    Container,
    ExpandableSection,
    FormField,
    Grid,
    Header,
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
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
    const [activeStepIndex, setActiveStepIndex] = useState(0);
    const [groupInput, setGroupInput] = useState('');

    const [
        createHostedMcpServer,
        { isLoading: isSaving, isSuccess, isError, error: createError }
    ] = useCreateHostedMcpServerMutation();

    useEffect(() => {
        if (!visible) {
            setFormState(INITIAL_FORM_STATE);
            setFieldErrors({});
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

    const validateStep = (stepIndex: number): Record<string, string> => {
        const errors: Record<string, string> = {};
        switch (stepIndex) {
            case 0: {
                if (!formState.name.trim()) {
                    errors.name = 'Name is required.';
                }
                if (!formState.startCommand.trim()) {
                    errors.startCommand = 'Start command is required.';
                }
                break;
            }
            case 1: {
                const min = Number(formState.minCapacity);
                const max = Number(formState.maxCapacity);
                if (Number.isNaN(min) || min < 1) {
                    errors.minCapacity = 'Minimum capacity must be a positive number.';
                }
                if (Number.isNaN(max) || max < 1) {
                    errors.maxCapacity = 'Maximum capacity must be a positive number.';
                }
                if (!Number.isNaN(min) && !Number.isNaN(max) && min > max) {
                    errors.maxCapacity = 'Maximum capacity must be greater than or equal to minimum capacity.';
                }
                break;
            }
            case 3: {
                if (!formState.healthCheckCommand.trim()) {
                    errors.healthCheckCommand = 'Container health check command is required.';
                }
                const containerNumericFields = [
                    { value: formState.healthCheckInterval, field: 'healthCheckInterval', label: 'Container health check interval' },
                    { value: formState.healthCheckTimeout, field: 'healthCheckTimeout', label: 'Container health check timeout' },
                    { value: formState.healthCheckRetries, field: 'healthCheckRetries', label: 'Container health check retries' },
                    { value: formState.healthCheckStartPeriod, field: 'healthCheckStartPeriod', label: 'Container health check start period' },
                ];
                containerNumericFields.forEach(({ value, field, label }) => {
                    if (value.trim() === '') {
                        errors[field] = `${label} is required.`;
                    } else if (Number.isNaN(Number(value))) {
                        errors[field] = `${label} must be a number.`;
                    }
                });

                if (!formState.lbPath.trim()) {
                    errors.lbPath = 'Load balancer health check path is required.';
                }
                const loadBalancerNumericFields = [
                    { value: formState.lbInterval, field: 'lbInterval', label: 'Load balancer health check interval' },
                    { value: formState.lbTimeout, field: 'lbTimeout', label: 'Load balancer health check timeout' },
                    { value: formState.lbHealthyThreshold, field: 'lbHealthyThreshold', label: 'Load balancer healthy threshold' },
                    { value: formState.lbUnhealthyThreshold, field: 'lbUnhealthyThreshold', label: 'Load balancer unhealthy threshold' },
                ];
                loadBalancerNumericFields.forEach(({ value, field, label }) => {
                    if (value.trim() === '') {
                        errors[field] = `${label} is required.`;
                    } else if (Number.isNaN(Number(value))) {
                        errors[field] = `${label} must be a number.`;
                    }
                });
                break;
            }
            default:
                break;
        }
        return errors;
    };

    const handleSubmit = async () => {
        const stepsToValidate = [0, 1, 3];
        const allErrors: Record<string, string> = {};
        stepsToValidate.forEach((step) => {
            Object.assign(allErrors, validateStep(step));
        });
        
        if (Object.keys(allErrors).length > 0) {
            setFieldErrors(allErrors);
            // Navigate to first step with errors
            if (allErrors.name || allErrors.startCommand) {
                setActiveStepIndex(0);
            } else if (allErrors.minCapacity || allErrors.maxCapacity) {
                setActiveStepIndex(1);
            } else if (Object.keys(allErrors).some(key => key.toLowerCase().includes('health') || key.includes('lb'))) {
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
                <SpaceBetween size='s'>
                    <FormField 
                        label='Name' 
                        description='Unique identifier for the hosted MCP server.'
                        errorText={fieldErrors.name}
                    >
                        <Input value={formState.name} onChange={onChange('name')} />
                    </FormField>
                    <FormField 
                        label={<span>Description <em>- Optional</em></span>}
                        description='Description of the MCP server.'
                    >
                        <Textarea value={formState.description} rows={3} onChange={onChange('description')} />
                    </FormField>
                    <FormField 
                        label='Server type'
                        description='Transport protocol for MCP communication.'
                    >
                        <Select
                            selectedOption={formState.serverType}
                            onChange={({ detail }) => setFormState((prev) => ({
                                ...prev,
                                serverType: detail.selectedOption,
                            }))}
                            options={SERVER_TYPE_OPTIONS}
                        />
                    </FormField>
                    <FormField 
                        label={<span>Base Image <em>- Optional</em></span>}
                        description='Pre-built image or base image URI.'
                        errorText={fieldErrors.image}
                    >
                        <Input 
                            value={formState.image} 
                            onChange={onChange('image')} 
                            placeholder='public.ecr.aws/... or registry/image:tag' 
                        />
                    </FormField>
                    <FormField
                        label='Start command'
                        description='Command executed when the container starts. For STDIO servers include the binary or script to launch.'
                        errorText={fieldErrors.startCommand}
                    >
                        <Textarea value={formState.startCommand} rows={4} onChange={onChange('startCommand')} />
                    </FormField>
                    <FormField
                        label={<span>Container Port <em>- Optional</em></span>}
                        description='Defaults to 8000 for HTTP/SSE or 8080 for STDIO proxy.'
                        errorText={fieldErrors.port}
                    >
                        <Input value={formState.port} onChange={onChange('port')} inputMode='numeric' type='number' placeholder={formState.serverType.label === 'STDIO' ? '8080' : '8000'}/>
                    </FormField>
                    <FormField
                        label={<span>Groups <em>- Optional</em></span>}
                        description='Restrict access to specific groups. Enter a group name and press return to add it.'
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
            isOptional: true,
            content: (
                <SpaceBetween size='s'>
                    <FormField 
                        label='Minimum capacity'
                        description='Minimum number of tasks to maintain.'
                        errorText={fieldErrors.minCapacity}
                    >
                        <Input value={formState.minCapacity} onChange={onChange('minCapacity')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField 
                        label='Maximum capacity'
                        description='Maximum number of tasks allowed to scale to.'
                        errorText={fieldErrors.maxCapacity}
                    >
                        <Input value={formState.maxCapacity} onChange={onChange('maxCapacity')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField 
                        label='Target value' 
                        description='Target metric value for scaling.'
                    >
                        <Input value={formState.targetValue} onChange={onChange('targetValue')} inputMode='numeric' type='number' />
                    </FormField>
                    <FormField 
                        label='Metric name' 
                        description='CloudWatch metric for scaling, e.g. RequestCount.'
                    >
                        <Input value={formState.metricName} onChange={onChange('metricName')} />
                    </FormField>
                    <FormField 
                        label='Scale duration' 
                        description='Period length for the CloudWatch metric.'
                    >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={formState.duration} onChange={onChange('duration')} inputMode='numeric' type='number' />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                    </FormField>
                    <FormField 
                        label='Cooldown' 
                        description='Cooldown between scaling events.'
                    >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={formState.cooldown} onChange={onChange('cooldown')} inputMode='numeric' type='number' />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                    </FormField>
                </SpaceBetween>
            ),
        },
        {
            title: 'Advanced options',
            description: 'Optional image, IAM roles, environment variables.',
            isOptional: true,
            content: (
                <SpaceBetween size='s'>
                    <FormField 
                        label='S3 artifact path' 
                        description='S3 URI for server artifacts.'
                    >
                        <Input value={formState.s3Path} onChange={onChange('s3Path')} placeholder='s3://bucket/path' />
                    </FormField>
                    <FormField 
                        label='CPU' 
                        description='Defaults to 256 units (0.25 vCPU).'
                    >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={formState.cpu} onChange={onChange('cpu')} inputMode='numeric' type='number' />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>units</span>
                    </Grid>
                    </FormField>
                    <FormField 
                        label='Memory' 
                        description='Defaults to 512 MiB.'
                    >
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={formState.memoryLimitMiB} onChange={onChange('memoryLimitMiB')} inputMode='numeric' type='number' />
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>MiB</span>
                    </Grid>
                    </FormField>
                    <FormField 
                        label='Task execution role ARN' 
                        description='IAM role for pulling images and reading S3.'
                    >
                        <Input value={formState.taskExecutionRoleArn} onChange={onChange('taskExecutionRoleArn')} />
                    </FormField>
                    <FormField 
                        label='Task role ARN' 
                        description='IAM role for the running task.'
                    >
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
                <SpaceBetween size='s'>
                    <Container
                        header={<Header variant='h2'>Container Health Check</Header>}
                    >
                        <SpaceBetween size='s'>
                            <FormField
                                label='Command'
                                description='Command executed inside the container to verify health. Use {{PORT}} to reference the container port.'
                                errorText={fieldErrors.healthCheckCommand}
                            >
                                <Input
                                    value={formState.healthCheckCommand}
                                    onChange={onChange('healthCheckCommand')}
                                    placeholder='CMD-SHELL curl --fail http://localhost:{{PORT}}/status || exit 1'
                                />
                            </FormField>
                            <FormField 
                                label='Interval' 
                                description='Time between running the health check.'
                                errorText={fieldErrors.healthCheckInterval}
                            >
                            <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                                <Input
                                    value={formState.healthCheckInterval}
                                    onChange={onChange('healthCheckInterval')}
                                    inputMode='numeric'
                                    type='number'
                                />
                                <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                            </Grid>
                            </FormField>
                            <FormField 
                                label='Timeout' 
                                description='Time to wait for a health check to succeed before considering it failed.'
                                errorText={fieldErrors.healthCheckTimeout}
                            >
                            <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                                <Input
                                    value={formState.healthCheckTimeout}
                                    onChange={onChange('healthCheckTimeout')}
                                    inputMode='numeric'
                                    type='number'
                                />
                                <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                            </Grid>
                            </FormField>
                            <FormField 
                                label='Retries'
                                description='Number of times to retry a failed health check before the container is considered unhealthy.'
                                errorText={fieldErrors.healthCheckRetries}
                            >
                                <Input
                                    value={formState.healthCheckRetries}
                                    onChange={onChange('healthCheckRetries')}
                                    inputMode='numeric'
                                    type='number'
                                />
                            </FormField>
                            <FormField 
                                label='Start period' 
                                description='Grace period before failed health checks count towards the maximum number of retries.'
                                errorText={fieldErrors.healthCheckStartPeriod}
                            >
                            <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                                <Input
                                    value={formState.healthCheckStartPeriod}
                                    onChange={onChange('healthCheckStartPeriod')}
                                    inputMode='numeric'
                                    type='number'
                                />
                                <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                            </Grid>
                            </FormField>
                        </SpaceBetween>
                    </Container>
                    <Container
                        header={<Header variant='h2'>Load Balancer Health Check</Header>}
                    >
                        <SpaceBetween size='s'>
                            <FormField
                                label='Path'
                                description='Relative path used by the load balancer to determine service health.'
                                errorText={fieldErrors.lbPath}
                            >
                                <Input
                                    value={formState.lbPath}
                                    onChange={onChange('lbPath')}
                                    placeholder='/status'
                                />
                            </FormField>
                            <FormField 
                                label='Interval' 
                                description='Time between health checks.'
                                errorText={fieldErrors.lbInterval}
                            >
                            <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                                <Input
                                    value={formState.lbInterval}
                                    onChange={onChange('lbInterval')}
                                    inputMode='numeric'
                                    type='number'
                                />
                                <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                            </Grid>
                            </FormField>
                            <FormField 
                                label='Timeout' 
                                description='Time to wait for a response before considering the health check failed.'
                                errorText={fieldErrors.lbTimeout}
                            >
                            <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                                <Input
                                    value={formState.lbTimeout}
                                    onChange={onChange('lbTimeout')}
                                    inputMode='numeric'
                                    type='number'
                                />
                                <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                            </Grid>
                            </FormField>
                            <FormField 
                                label='Healthy threshold'
                                description='Number of consecutive successful health checks before considering the target healthy.'
                                errorText={fieldErrors.lbHealthyThreshold}
                            >
                                <Input
                                    value={formState.lbHealthyThreshold}
                                    onChange={onChange('lbHealthyThreshold')}
                                    inputMode='numeric'
                                    type='number'
                                />
                            </FormField>
                            <FormField 
                                label='Unhealthy threshold'
                                description='Number of consecutive failed health checks before considering the target unhealthy.'
                                errorText={fieldErrors.lbUnhealthyThreshold}
                            >
                                <Input
                                    value={formState.lbUnhealthyThreshold}
                                    onChange={onChange('lbUnhealthyThreshold')}
                                    inputMode='numeric'
                                    type='number'
                                />
                            </FormField>
                        </SpaceBetween>
                    </Container>
                </SpaceBetween>
            ),
        },
        {
            title: 'Review & create',
            description: 'Review configuration before provisioning the hosted MCP server.',
            content: (
                <SpaceBetween size='l'>
                    <ExpandableSection headerText='Server details' defaultExpanded={true}>
                        <SpaceBetween size='xs'>
                            <Box><strong>Name:</strong> {formState.name || '-'}</Box>
                            <Box><strong>Description:</strong> {formState.description || '-'}</Box>
                            <Box><strong>Server type:</strong> {formState.serverType.label}</Box>
                            <Box><strong>Base image:</strong> {formState.image || '-'}</Box>
                            <Box><strong>Start command:</strong> <div><code>{formState.startCommand || '-'}</code></div></Box>
                            <Box><strong>Container port:</strong> {formState.port || '8000 (default)'}</Box>
                            <Box><strong>Groups:</strong> {formState.groups.length ? formState.groups.join(', ') : '(public)'}</Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Scaling configuration' defaultExpanded={false}>
                        <SpaceBetween size='xs'>
                            <Box><strong>Min capacity:</strong> {formState.minCapacity}</Box>
                            <Box><strong>Max capacity:</strong> {formState.maxCapacity}</Box>
                            <Box><strong>Target value:</strong> {formState.targetValue || '-'}</Box>
                            <Box><strong>Metric name:</strong> {formState.metricName || '-'}</Box>
                            <Box><strong>Duration:</strong> {formState.duration ? `${formState.duration}s` : '-'}</Box>
                            <Box><strong>Cooldown:</strong> {formState.cooldown ? `${formState.cooldown}s` : '-'}</Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Advanced options' defaultExpanded={false}>
                        <SpaceBetween size='xs'>
                            <Box><strong>S3 artifact path:</strong> {formState.s3Path || '-'}</Box>
                            <Box><strong>CPU:</strong> {formState.cpu ? `${formState.cpu} units` : '256 units (default)'}</Box>
                            <Box><strong>Memory:</strong> {formState.memoryLimitMiB ? `${formState.memoryLimitMiB} MiB` : '512 MiB (default)'}</Box>
                            <Box><strong>Task execution role ARN:</strong> {formState.taskExecutionRoleArn || '-'}</Box>
                            <Box><strong>Task role ARN:</strong> {formState.taskRoleArn || '-'}</Box>
                            <Box><strong>Environment variables:</strong> {formState.environment.length ? formState.environment.map(({ key, value }) => `${key}=${value}`).join(', ') : 'None'}</Box>
                        </SpaceBetween>
                    </ExpandableSection>
                    <ExpandableSection headerText='Health checks' defaultExpanded={false}>
                        <SpaceBetween size='m'>
                            <div>
                                <Header variant='h3'>Container Health Check</Header>
                                <SpaceBetween size='xs'>
                                    <Box><strong>Command:</strong> {formState.healthCheckCommand}</Box>
                                    <Box><strong>Interval:</strong> {formState.healthCheckInterval}s</Box>
                                    <Box><strong>Timeout:</strong> {formState.healthCheckTimeout}s</Box>
                                    <Box><strong>Retries:</strong> {formState.healthCheckRetries}</Box>
                                    <Box><strong>Start period:</strong> {formState.healthCheckStartPeriod}s</Box>
                                </SpaceBetween>
                            </div>
                            <div>
                                <Header variant='h3'>Load Balancer Health Check</Header>
                                <SpaceBetween size='xs'>
                                    <Box><strong>Path:</strong> {formState.lbPath}</Box>
                                    <Box><strong>Interval:</strong> {formState.lbInterval}s</Box>
                                    <Box><strong>Timeout:</strong> {formState.lbTimeout}s</Box>
                                    <Box><strong>Healthy threshold:</strong> {formState.lbHealthyThreshold}</Box>
                                    <Box><strong>Unhealthy threshold:</strong> {formState.lbUnhealthyThreshold}</Box>
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
            onDismiss={() => setVisible(false)}
            header='Create hosted MCP server'
            size='large'
        >
            <Wizard
                    steps={steps}
                    activeStepIndex={activeStepIndex}
                    submitButtonText='Create server'
                    isLoadingNextStep={isSaving}
                    allowSkipTo
                    i18nStrings={{
                        stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                        collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                        skipToButtonLabel: () => 'Skip to Create',
                        navigationAriaLabel: 'Steps',
                        cancelButton: 'Cancel',
                        previousButton: 'Previous',
                        nextButton: 'Next',
                        optional: 'Optional',
                    }}
                    onNavigate={({ detail }) => {
                        const { reason, requestedStepIndex } = detail;
                        if (reason === 'next' || reason === 'skip') {
                            const currentErrors = validateStep(activeStepIndex);
                            if (Object.keys(currentErrors).length > 0) {
                                setFieldErrors(currentErrors);
                                return;
                            }
                            setFieldErrors({});
                        } else if (reason === 'previous' || reason === 'step') {
                            setFieldErrors({});
                        }
                        setActiveStepIndex(requestedStepIndex);
                    }}
                    onCancel={() => setVisible(false)}
                    onSubmit={() => handleSubmit()}
                />
        </Modal>
    );
}

export default CreateHostedMcpServerModal;
