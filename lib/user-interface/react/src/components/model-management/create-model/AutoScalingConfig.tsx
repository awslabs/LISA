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

import { IAutoScalingConfig } from '../../../shared/model/model-management.model';
import { Header, SpaceBetween } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';

export function AutoScalingConfig (props: FormProps<IAutoScalingConfig>) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <Container
                header={
                    <Header variant='h3'>Auto Scaling Capacity</Header>
                }
            >
                <FormField label='Min Capacity' errorText={props.formErrors?.autoScalingConfig?.minCapacity}>
                    <Input value={props.item.minCapacity.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.minCapacity'])} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.minCapacity': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Max Capacity' errorText={props.formErrors?.autoScalingConfig?.maxCapacity}>
                    <Input value={props.item.maxCapacity.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.maxCapacity'])} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.maxCapacity': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Cooldown' errorText={props.formErrors?.autoScalingConfig?.cooldown}>
                    <Input value={props.item.cooldown.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.cooldown'])} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.Cooldown': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Default Instance Warmup' errorText={props.formErrors?.autoScalingConfig?.defaultInstanceWarmup}>
                    <Input value={props.item.defaultInstanceWarmup.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.defaultInstanceWarmup'])} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.defaultInstanceWarmup': Number(detail.value) });
                    }}/>
                </FormField>
            </Container>
            <Container
                header={
                    <Header variant='h3'>Metric Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='ALB Metric Name' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.albMetricName}>
                        <Input value={props.item.metricConfig.albMetricName} inputMode='text' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.albMetricName'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.albMetricName': detail.value });
                        }}/>
                    </FormField>
                    <FormField label='Target Value' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.targetValue}>
                        <Input value={props.item.metricConfig.targetValue.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.targetValue'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.targetValue': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Duration' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.duration}>
                        <Input value={props.item.metricConfig.duration.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.duration'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.duration': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Estimated Instance Warmup' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.estimatedInstanceWarmup}>
                        <Input value={props.item.metricConfig.estimatedInstanceWarmup.toString()} inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.estimatedInstanceWarmup'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.estimatedInstanceWarmup': Number(detail.value) });
                        }}/>
                    </FormField>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
