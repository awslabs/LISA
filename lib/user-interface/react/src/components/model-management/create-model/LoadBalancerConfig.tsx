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
import { Grid, Header } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';

export function LoadBalancerConfig (props: FormProps<ILoadBalancerConfig>) : ReactElement {
    return (
        <>
            <Container
                header={
                    <Header variant='h2'>Health Check Config</Header>
                }
            >
                <FormField label='Path' errorText={props.formErrors?.loadBalancerConfig?.healthCheckConfig?.path}>
                    <Input value={props.item.healthCheckConfig.path} inputMode='text' onBlur={() => props.touchFields(['loadBalancerConfig.healthCheckConfig.path'])} onChange={({ detail }) => {
                        props.setFields({ 'loadBalancerConfig.healthCheckConfig.path': detail.value });
                    }}/>
                </FormField>
                <FormField label='Interval' errorText={props.formErrors?.loadBalancerConfig?.healthCheckConfig?.interval}>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.healthCheckConfig.interval.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['loadBalancerConfig.healthCheckConfig.interval'])} onChange={({ detail }) => {
                            props.setFields({ 'loadBalancerConfig.healthCheckConfig.interval': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </FormField>
                <FormField label='Timeout' errorText={props.formErrors?.loadBalancerConfig?.healthCheckConfig?.timeout}>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.healthCheckConfig.timeout.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['loadBalancerConfig.healthCheckConfig.timeout'])} onChange={({ detail }) => {
                            props.setFields({ 'loadBalancerConfig.healthCheckConfig.timeout': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </FormField>
                <FormField label='Healthy Threshold Count' errorText={props.formErrors?.loadBalancerConfig?.healthCheckConfig?.healthyThresholdCount}>
                    <Input value={props.item.healthCheckConfig.healthyThresholdCount.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['loadBalancerConfig.healthCheckConfig.healthyThresholdCount'])} onChange={({ detail }) => {
                        props.setFields({ 'loadBalancerConfig.healthCheckConfig.healthyThresholdCount': Number(detail.value) });
                    }}/>
                </FormField>
                <FormField label='Unhealthy Threshold Count' errorText={props.formErrors?.loadBalancerConfig?.healthCheckConfig?.unhealthyThresholdCount}>
                    <Input value={props.item.healthCheckConfig.unhealthyThresholdCount.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['loadBalancerConfig.healthCheckConfig.unhealthyThresholdCount'])} onChange={({ detail }) => {
                        props.setFields({ 'loadBalancerConfig.healthCheckConfig.unhealthyThresholdCount': Number(detail.value) });
                    }}/>
                </FormField>
            </Container>
        </>
    );
}
