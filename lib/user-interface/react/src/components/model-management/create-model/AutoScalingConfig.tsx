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
            <FormField label='Min Capacity' errorText={props.formErrors?.AutoScalingConfig?.MinCapacity}>
                <Input value={props.item.MinCapacity.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.MinCapacity'])} onChange={({ detail }) => {
                    props.setFields({ 'AutoScalingConfig.MinCapacity': Number(detail.value) });
                }}/>
            </FormField>
            <FormField label='Max Capacity' errorText={props.formErrors?.AutoScalingConfig?.MaxCapacity}>
                <Input value={props.item.MaxCapacity.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.MaxCapacity'])} onChange={({ detail }) => {
                    props.setFields({ 'AutoScalingConfig.MaxCapacity': Number(detail.value) });
                }}/>
            </FormField>
            <FormField label='Cooldown' errorText={props.formErrors?.AutoScalingConfig?.Cooldown}>
                <Input value={props.item.Cooldown.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.Cooldown'])} onChange={({ detail }) => {
                    props.setFields({ 'AutoScalingConfig.Cooldown': Number(detail.value) });
                }}/>
            </FormField>
            <FormField label='Default Instance Warmup' errorText={props.formErrors?.AutoScalingConfig?.DefaultInstanceWarmup}>
                <Input value={props.item.DefaultInstanceWarmup.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.DefaultInstanceWarmup'])} onChange={({ detail }) => {
                    props.setFields({ 'AutoScalingConfig.DefaultInstanceWarmup': Number(detail.value) });
                }}/>
            </FormField>
            <Container
                header={
                    <Header variant='h3'>Metric Config</Header>
                }
            >
                <SpaceBetween size={'s'}>
                    <FormField label='ALB Metric Name' errorText={props.formErrors?.AutoScalingConfig?.MetricConfig?.AlbMetricName}>
                        <Input value={props.item.MetricConfig.AlbMetricName} inputMode='text' onBlur={() => props.touchFields(['AutoScalingConfig.MetricConfig.AlbMetricName'])} onChange={({ detail }) => {
                            props.setFields({ 'AutoScalingConfig.MetricConfig.AlbMetricName': detail.value });
                        }}/>
                    </FormField>
                    <FormField label='Target Value' errorText={props.formErrors?.AutoScalingConfig?.MetricConfig?.TargetValue}>
                        <Input value={props.item.MetricConfig.TargetValue.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.MetricConfig.TargetValue'])} onChange={({ detail }) => {
                            props.setFields({ 'AutoScalingConfig.MetricConfig.TargetValue': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Duration' errorText={props.formErrors?.AutoScalingConfig?.MetricConfig?.Duration}>
                        <Input value={props.item.MetricConfig.Duration.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.MetricConfig.Duration'])} onChange={({ detail }) => {
                            props.setFields({ 'AutoScalingConfig.MetricConfig.Duration': Number(detail.value) });
                        }}/>
                    </FormField>
                    <FormField label='Estimated Instance Warmup' errorText={props.formErrors?.AutoScalingConfig?.MetricConfig?.EstimatedInstanceWarmup}>
                        <Input value={props.item.MetricConfig.EstimatedInstanceWarmup.toString()} inputMode='numeric' onBlur={() => props.touchFields(['AutoScalingConfig.MetricConfig.EstimatedInstanceWarmup'])} onChange={({ detail }) => {
                            props.setFields({ 'AutoScalingConfig.MetricConfig.EstimatedInstanceWarmup': Number(detail.value) });
                        }}/>
                    </FormField>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
