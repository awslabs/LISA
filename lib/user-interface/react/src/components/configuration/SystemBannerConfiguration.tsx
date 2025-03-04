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

import {
    Container,
    FormField,
    Grid,
    Header,
    Input,
    SpaceBetween,
    Toggle
} from '@cloudscape-design/components';
import React from 'react';
import { SetFieldsFunction, TouchFieldsFunction } from '../../shared/validation';

export type SystemBannerConfigurationProps = {
    setFields: SetFieldsFunction;
    textColor: string;
    backgroundColor: string;
    text: string;
    isEnabled: boolean;
    touchFields: TouchFieldsFunction;
    errors: any;
};

export function SystemBannerConfiguration (props: SystemBannerConfigurationProps) {
    return (
        <Container
            header={
                <Header variant='h2'>
                    System Banner
                </Header>
            }>
            <SpaceBetween direction='vertical' size='l'>
                <FormField
                    label='Banner Text'
                    errorText={props.errors?.systemBanner?.text}
                >
                    <Input
                        onChange={({detail}) => {
                            props.setFields({'systemBanner.text': detail.value});
                        }}
                        onBlur={() => props.touchFields(['systemBanner.text'])}
                        value={props.text}
                        placeholder='Enter system banner text'
                        disabled={!props.isEnabled}
                    />
                </FormField>
                <Toggle
                    onChange={({detail}) => {
                        props.setFields({'systemBanner.isEnabled': detail.checked});
                    }}
                    checked={props.isEnabled!}
                >
                    Activate System Banner
                </Toggle>
                <FormField>
                    <Grid gridDefinition={[{colspan: 1}, {colspan: 2}]}>
                        <input
                            type='color'
                            onInput={(event) =>
                                props.setFields({'systemBanner.textColor': event.target.value})
                            }
                            value={props.textColor}
                            disabled={!props.isEnabled}
                            style={{
                                border: '2px solid #7F8897',
                                borderRadius: '6px',
                                padding: '3px'
                            }}
                        />
                        <p>Text Color</p>
                    </Grid>
                </FormField>
                <FormField>
                    <Grid gridDefinition={[{colspan: 1}, {colspan: 2}]}>
                        <input
                            type='color'
                            onInput={(event) =>
                                props.setFields({'systemBanner.backgroundColor': event.target.value})
                            }
                            value={props.backgroundColor}
                            disabled={!props.isEnabled}
                            style={{
                                border: '2px solid #7F8897',
                                borderRadius: '6px',
                                padding: '3px'
                            }}
                        />
                        <p>Background Color</p>
                    </Grid>
                </FormField>
            </SpaceBetween>
        </Container>
    );
}

export default SystemBannerConfiguration;
