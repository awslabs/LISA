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
    Header,
    Input,
    SpaceBetween,
    Toggle
} from '@cloudscape-design/components';
import React from 'react';
import { SetFieldsFunction, TouchFieldsFunction } from '../../shared/validation';

export type AnnouncementConfigurationProps = {
    setFields: SetFieldsFunction;
    touchFields: TouchFieldsFunction;
    errors: any;
    isEnabled: boolean;
    message: string;
};

export function AnnouncementConfiguration (props: AnnouncementConfigurationProps) {
    return (
        <Container
            header={
                <Header variant='h2'>
                    Announcements
                </Header>
            }>
            <SpaceBetween direction='vertical' size='l'>
                <Toggle
                    onChange={({detail}) => {
                        props.setFields({'announcement.isEnabled': detail.checked});
                    }}
                    checked={props.isEnabled!}
                >
                    Activate Announcement
                </Toggle>
                <FormField
                    label='Announcement Message'
                    errorText={props.errors?.announcement?.message}
                >
                    <Input
                        onChange={({detail}) => {
                            props.setFields({'announcement.message': detail.value});
                        }}
                        onBlur={() => props.touchFields(['announcement.message'])}
                        value={props.message}
                        placeholder='Enter announcement message'
                        disabled={!props.isEnabled}
                    />
                </FormField>
            </SpaceBetween>
        </Container>
    );
}

export default AnnouncementConfiguration;
