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
import { ILoadBalancerConfig } from '../../../shared/model/model-management.model';
import { Header } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';

export function LoadBalancerConfig (props: FormProps<ILoadBalancerConfig>) : ReactElement {
    return (
        <>
            <Container
                header={
                    <Header variant='h2'>Health Check Config</Header>
                }
            >
                <FormField label='Path' errorText={props.formErrors?.LoadBalancerConfig?.HealthCheckConfig?.Path}>
                    <Input value={props.item.HealthCheckConfig.Path} inputMode='text' onBlur={() => props.touchFields(['LoadBalancerConfig.HealthCheckConfig.Path'])} onChange={({ detail }) => {
                        props.setFields({ 'LoadBalancerConfig.HealthCheckConfig.Path': detail.value });
                    }}/>
                </FormField>
                <FormField label='Interval' errorText={props.formErrors?.LoadBalancerConfig?.HealthCheckConfig?.Interval}>
                    <Input value={props.item.HealthCheckConfig.Interval.toString()} inputMode='numeric' onBlur={() => props.touchFields(['LoadBalancerConfig.HealthCheckConfig.Interval'])} onChange={({ detail }) => {
                        props.setFields({ 'LoadBalancerConfig.HealthCheckConfig.Interval': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Timeout' errorText={props.formErrors?.LoadBalancerConfig?.HealthCheckConfig?.Timeout}>
                    <Input value={props.item.HealthCheckConfig.Timeout.toString()} inputMode='numeric' onBlur={() => props.touchFields(['LoadBalancerConfig.HealthCheckConfig.Timeout'])} onChange={({ detail }) => {
                        props.setFields({ 'LoadBalancerConfig.HealthCheckConfig.Timeout': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Healthy Threshold Count' errorText={props.formErrors?.LoadBalancerConfig?.HealthCheckConfig?.HealthyThresholdCount}>
                    <Input value={props.item.HealthCheckConfig.HealthyThresholdCount.toString()} inputMode='numeric' onBlur={() => props.touchFields(['LoadBalancerConfig.HealthCheckConfig.HealthyThresholdCount'])} onChange={({ detail }) => {
                        props.setFields({ 'LoadBalancerConfig.HealthCheckConfig.HealthyThresholdCount': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Unhealthy Threshold Count' errorText={props.formErrors?.LoadBalancerConfig?.HealthCheckConfig?.UnhealthyThresholdCount}>
                    <Input value={props.item.HealthCheckConfig.UnhealthyThresholdCount.toString()} inputMode='numeric' onBlur={() => props.touchFields(['LoadBalancerConfig.HealthCheckConfig.UnhealthyThresholdCount'])} onChange={({ detail }) => {
                        props.setFields({ 'LoadBalancerConfig.HealthCheckConfig.UnhealthyThresholdCount': Number(detail.value) });
                    }}/>
                </FormField>
            </Container>
        </>
    );
}
