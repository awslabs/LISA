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
import { Grid, Header, SpaceBetween } from '@cloudscape-design/components';
import Container from '@cloudscape-design/components/container';

type AutoScalingConfigProps = FormProps<IAutoScalingConfig> & {
    isEdit: boolean
};

export function AutoScalingConfig (props: AutoScalingConfigProps) : ReactElement {
    return (
        <SpaceBetween size={'s'}>
            <Container
                header={<Header variant='h3'>Auto Scaling Capacity</Header>}>
                <SpaceBetween size={'s'}>
                    <FormField label='Block Device Volume Size' errorText={props.formErrors?.autoScalingConfig?.blockDeviceVolumeSize}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.blockDeviceVolumeSize.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.blockDeviceVolumeSize'])} disabled={props.isEdit} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.blockDeviceVolumeSize': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>GBs</span>
                    </Grid>
                    <FormField label='Min Capacity' errorText={props.formErrors?.autoScalingConfig?.minCapacity}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.minCapacity.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.minCapacity'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.minCapacity': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                    </Grid>
                    <FormField label='Max Capacity' errorText={props.formErrors?.autoScalingConfig?.maxCapacity}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.maxCapacity.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.maxCapacity'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.maxCapacity': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                    </Grid>
                    <FormField label='Desired Capacity' errorText={props.formErrors?.autoScalingConfig?.desiredCapacity}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={String(props.item.desiredCapacity)} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.desiredCapacity'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.desiredCapacity': detail.value.trim().length > 0 ? Number(detail.value) : undefined });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>instances</span>
                    </Grid>
                    <FormField label='Cooldown' errorText={props.formErrors?.autoScalingConfig?.cooldown}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.cooldown.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.cooldown'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.cooldown': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                    <FormField label='Default Instance Warmup' errorText={props.formErrors?.autoScalingConfig?.defaultInstanceWarmup}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.defaultInstanceWarmup.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.defaultInstanceWarmup'])} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.defaultInstanceWarmup': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </SpaceBetween>
            </Container>
            <Container
                header={<Header variant='h3'>Metric Config</Header>}>
                <SpaceBetween size={'s'}>
                    <FormField label='ALB Metric Name' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.albMetricName}>
                    </FormField>
                    <Input value={props.item.metricConfig.albMetricName} inputMode='text' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.albMetricName'])} disabled={props.isEdit} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.metricConfig.albMetricName': detail.value });
                    }}/>
                    <FormField label='Target Value' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.targetValue}>
                    </FormField>
                    <Input value={props.item.metricConfig.targetValue.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.targetValue'])} disabled={props.isEdit} onChange={({ detail }) => {
                        props.setFields({ 'autoScalingConfig.metricConfig.targetValue': Number(detail.value) });
                    }}/>
                    <FormField label='Duration' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.duration}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.metricConfig.duration.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.duration'])} disabled={props.isEdit} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.duration': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                    <FormField label='Estimated Instance Warmup' errorText={props.formErrors?.autoScalingConfig?.metricConfig?.estimatedInstanceWarmup}>
                    </FormField>
                    <Grid gridDefinition={[{colspan: 10}, {colspan: 2}]} disableGutters={true}>
                        <Input value={props.item.metricConfig.estimatedInstanceWarmup.toString()} type='number' inputMode='numeric' onBlur={() => props.touchFields(['autoScalingConfig.metricConfig.estimatedInstanceWarmup'])} disabled={props.isEdit} onChange={({ detail }) => {
                            props.setFields({ 'autoScalingConfig.metricConfig.estimatedInstanceWarmup': Number(detail.value) });
                        }}/>
                        <span style={{lineHeight: '2.5em', paddingLeft: '0.5em'}}>seconds</span>
                    </Grid>
                </SpaceBetween>
            </Container>
        </SpaceBetween>
    );
}
