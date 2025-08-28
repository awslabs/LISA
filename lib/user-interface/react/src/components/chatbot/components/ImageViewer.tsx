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
    ButtonDropdown,
    Grid,
    Header,
    Modal,
    SpaceBetween,
} from '@cloudscape-design/components';

import { MessageContentComplex } from '@langchain/core/dist/messages/base';
import { LisaChatMessageMetadata } from '@/components/types';
import React from 'react';
import { base64ToBlob, fetchImage } from '@/components/utils';
import { downloadFile } from '@/shared/util/downloader';

export type ImageViewerProps = {
    setVisible: (boolean) => void;
    visible: boolean;
    selectedImage: MessageContentComplex;
    metadata: LisaChatMessageMetadata
};

export default function ImageViewer ({visible, setVisible, selectedImage, metadata}: ImageViewerProps) {

    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            header={<Header variant='h1'>Image Details</Header>}
            footer=''
            size='large'
        >
            <SpaceBetween direction='vertical' size='l'>
                <Grid gridDefinition={[{ colspan: 11 }, { colspan: 1 }]}>
                    <img src={selectedImage?.image_url.url} alt='AI Generated' style={{ maxWidth:  '100%',  maxHeight: '100%', marginTop: '8px' }} />
                    <ButtonDropdown
                        items={[
                            { id: 'download-image', text: 'Download Image', iconName: 'download'},
                            { id: 'copy-image', text: 'Copy Image', iconName: 'copy'},
                            { id: 'copy-prompt', text: 'Copy Prompt', iconName: 'contact'}
                        ]}
                        ariaLabel='Control instance'
                        variant='icon'
                        onItemClick={async (e) => {
                            if (e.detail.id === 'download-image'){
                                const file = selectedImage.image_url.url.startsWith('https://') ?
                                    await fetchImage(selectedImage.image_url.url)
                                    : base64ToBlob(selectedImage.image_url.url.split(',')[1], 'image/png');
                                downloadFile(URL.createObjectURL(file), `${metadata?.imageGenerationParams?.prompt}.png`);
                            } else if (e.detail.id === 'copy-image') {
                                const copy = new ClipboardItem({ 'image/png':selectedImage.image_url.url.startsWith('https://') ?
                                    await fetchImage(selectedImage.image_url.url) : base64ToBlob(selectedImage.image_url.url.split(',')[1], 'image/png') });
                                await navigator.clipboard.write([copy]);
                            } else if (e.detail.id === 'copy-prompt') {
                                await navigator.clipboard.writeText(metadata?.imageGenerationParams?.prompt);
                            }
                        }}
                    />
                </Grid>
            </SpaceBetween>
        </Modal>
    );
}
