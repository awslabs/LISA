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

import { IAutoScalingConfig, ScheduleType } from '../../../shared/model/model-management.model';
import { Grid, Header, SpaceBetween } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';
import { ScheduleConfig } from './ScheduleConfig';

type AutoScalingConfigProps = FormProps<IAutoScalingConfig> & {
    isEdit: boolean
};

export function AutoScalingConfig (props: AutoScalingConfigProps) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <ScheduleConfig
                item={props.item.scheduling || {
                    scheduleEnabled: false,
                    scheduleType: ScheduleType.NONE,
                    timezone: 'UTC'
                }}
                setFields={(fields) => {
                    const scheduleFields: Record<string, any> = {};
                    Object.entries(fields).forEach(([key, value]) => {
                        scheduleFields[`autoScalingConfig.scheduling.${key}`] = value;
                    });
                    props.setFields(scheduleFields);
                }}
                touchFields={(fields) => {
                    const scheduleFields = fields.map((field) => `autoScalingConfig.scheduling.${field}`);
                    props.touchFields(scheduleFields);
                }}
                formErrors={props.formErrors?.autoScalingConfig?.scheduling}
                isEdit={props.isEdit}
            />
            <Container
                header={<Header variant='h3'>Auto Scaling Capacity</Header>}>
                <SpaceBetween size={'s'}>
                    <FormField
                        label='Block Device Volume Size'
                        description='Size of the EBS volume attached to each instance for model storage and cache.'
                        errorText={props.formErrors?.autoScalingConfig?.blockDeviceVolumeSize}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.blockDeviceVolumeSize.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.blockDeviceVolumeSize'])} disabled={props.isEdit} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.blockDeviceVolumeSize': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>GBs</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Min Capacity'
                        description='Minimum number of instances to maintain in the auto scaling group.'
                        errorText={props.formErrors?.autoScalingConfig?.minCapacity}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.minCapacity.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.minCapacity'])} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.minCapacity': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Max Capacity'
                        description='Maximum number of instances allowed in the auto scaling group.'
                        errorText={props.formErrors?.autoScalingConfig?.maxCapacity}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.maxCapacity.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.maxCapacity'])} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.maxCapacity': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Desired Capacity'
                        description='Target number of instances to maintain. Must be between min and max capacity.'
                        errorText={props.formErrors?.autoScalingConfig?.desiredCapacity}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={String(props.item.desiredCapacity)} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.desiredCapacity'])} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.desiredCapacity': detail.value.trim().length > 0 ? Number(detail.value) : undefined });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Cooldown'
                        description='Time to wait between scaling activities to allow metrics to stabilize.'
                        errorText={props.formErrors?.autoScalingConfig?.cooldown}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.cooldown.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.cooldown'])} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.cooldown': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Default Instance Warmup'
                        description='Time for new instances to warm up before receiving traffic and contributing to metrics.'
                        errorText={props.formErrors?.autoScalingConfig?.defaultInstanceWarmup}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.defaultInstanceWarmup.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.defaultInstanceWarmup'])} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.defaultInstanceWarmup': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                </SpaceBetween>
            </Container>
            <Container
                header={<Header variant='h3'>Metric Config</Header>}>
                <SpaceBetween size={'s'}>
                    <FormField
                        label='ALB Metric Name'
                        description='CloudWatch metric name for Application Load Balancer scaling decisions (e.g., RequestCountPerTarget).'
                        errorText={props.formErrors?.autoScalingConfig?.metricConfig?.albMetricName}
                    >
                        <Input value={props.item.metricConfig.albMetricName} inputMode='text' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.albMetricName'])} disabled={props.isEdit} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.albMetricName': detail.value });
                        }}/>
                    </FormField>
                    <FormField
                        label='Target Value'
                        description='Target value for the scaling metric. Auto scaling adjusts capacity to maintain this target.'
                        errorText={props.formErrors?.autoScalingConfig?.metricConfig?.targetValue}
                    >
                        <Input value={props.item.metricConfig.targetValue.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.targetValue'])} disabled={props.isEdit} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.targetValue': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField
                        label='Duration'
                        description='Period length for evaluating the CloudWatch metric before triggering scaling actions.'
                        errorText={props.formErrors?.autoScalingConfig?.metricConfig?.duration}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.metricConfig.duration.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.duration'])} disabled={props.isEdit} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.metricConfig.duration': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                    <FormField
                        label='Estimated Instance Warmup'
                        description='Estimated time for instances to be ready to serve traffic and contribute to scaling metrics.'
                        errorText={props.formErrors?.autoScalingConfig?.metricConfig?.estimatedInstanceWarmup}
                    >
                        <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                            <Input value={props.item.metricConfig.estimatedInstanceWarmup.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.estimatedInstanceWarmup'])} disabled={props.isEdit} onChange={({ detail }) => {
                                props.setFields({ 'autoScalingConfig.metricConfig.estimatedInstanceWarmup': Number(detail.value) });
                            }}/>
                            <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                        </Grid>
                    </FormField>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
