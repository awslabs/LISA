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

import Container from '@cloudscape-design/components/container';
import TextContent from '@cloudscape-design/components/text-content';
import ReactMarkdown from 'react-markdown';
import Spinner from '@cloudscape-design/components/spinner';
import Box from '@cloudscape-design/components/box';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { Button, Grid, SpaceBetween } from '@cloudscape-design/components';
import { JsonView, darkStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';
import { LisaChatMessage } from '../types';
import { useAppSelector } from '../../config/store';
import { selectCurrentUsername } from '../../shared/reducers/user.reducer';
import Avatar from 'react-avatar';

type MessageProps = {
    message?: LisaChatMessage;
    isRunning: boolean;
    showMetadata?: boolean;
};

export default function Message ({ message, isRunning, showMetadata }: MessageProps) {
    const currentUser = useAppSelector(selectCurrentUsername);
    return (
        <div className='mt-2' style={{overflow: 'hidden'}}>
            {isRunning && (
                <Grid gridDefinition={[{colspan: 1}, {colspan: 11}]}>
                    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-end', height: '100%'}} title={message?.metadata?.modelName}>
                        <Avatar size='40' round={true} color='#ff7f0e'/>
                    </div>
                    <Container>
                        <Box float='left'>
                            <Spinner/>
                        </Box>
                    </Container>
                </Grid>
            )}
            {message?.type !== 'human' && !isRunning && (
                <Grid gridDefinition={[{colspan: 1}, {colspan: 11}]}>
                    <div style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-end', height: '100%'}} title={message?.metadata?.modelName}>
                        <Avatar size='40' round={true} color='#ff7f0e'/>
                    </div>
                    <Container>
                        <SpaceBetween size='s' direction='vertical'>
                            <Grid gridDefinition={[{colspan: 11}, {colspan: 1}]}>
                                <ReactMarkdown children={message.content}/>
                                <div style={{display: 'flex', alignItems: 'center', height: '100%', justifyContent: 'flex-end'}}>
                                    <Button
                                        onClick={() => {
                                            navigator.clipboard.writeText(message.content);
                                        }}
                                        iconAlign='right'
                                        iconName='copy'
                                        variant='link'
                                    />
                                </div>
                            </Grid>
                            {message.metadata && showMetadata && (
                                <ExpandableSection variant='footer' headerText='Metadata'>
                                    <JsonView data={message.metadata} style={darkStyles}/>
                                </ExpandableSection>
                            )}
                        </SpaceBetween>
                    </Container>
                </Grid>
            )}
            {message?.type === 'human' && (
                <Grid gridDefinition={[{colspan: 11}, {colspan: 1}]}>
                    <Container>
                        <SpaceBetween size='s' alignItems='end'>
                            <TextContent>
                                <strong>{message.content}</strong>
                            </TextContent>
                        </SpaceBetween>
                    </Container>
                    <div style={{display: 'flex', alignItems: 'center', height: '100%'}} title={currentUser}>
                        <Avatar name={currentUser} size='40' round={true} />
                    </div>
                </Grid>
            )}
        </div>
    );
}
