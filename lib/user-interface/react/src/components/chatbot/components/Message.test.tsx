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

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { Mode } from '@cloudscape-design/global-styles';

import { Message } from './Message';
import ColorSchemeContext from '@/shared/color-scheme.provider';
import { selectCurrentUsername } from '@/shared/reducers/user.reducer';
import { LisaChatMessage, MessageTypes } from '../../types';

vi.mock('@/config/store', () => ({
    useAppDispatch: vi.fn(() => vi.fn()),
    useAppSelector: vi.fn(),
}));

const mockStore = configureStore({
    reducer: {
        user: () => ({
            currentUser: { name: 'TestUser' },
        }),
    },
});

const mockColorSchemeContext = {
    colorScheme: Mode.Light,
    setColorScheme: vi.fn(),
};

const baseProps = {
    isRunning: false,
    callingToolName: '',
    showMetadata: false,
    isStreaming: false,
    markdownDisplay: true,
    setChatConfiguration: vi.fn(),
    handleSendGenerateRequest: vi.fn(),
    setUserPrompt: vi.fn(),
    chatConfiguration: {} as any,
    onOpenDocument: vi.fn(),
};

const renderMessage = (message: LisaChatMessage) => {
    return render(
        <Provider store={mockStore}>
            <MemoryRouter>
                <ColorSchemeContext.Provider value={mockColorSchemeContext}>
                    <Message {...baseProps} message={message} />
                </ColorSchemeContext.Provider>
            </MemoryRouter>
        </Provider>
    );
};

describe('Message - Citations similarity scores', () => {
    beforeEach(async () => {
        vi.clearAllMocks();
        const storeModule = await import('@/config/store');
        (storeModule.useAppSelector as any).mockImplementation((selector: any) => {
            if (selector === selectCurrentUsername) return 'TestUser';
            return undefined;
        });
    });

    it('does not render similarity score badge inline (scores shown only in metadata)', () => {
        const message: LisaChatMessage = {
            type: MessageTypes.AI,
            content: 'Here is the answer',
            metadata: {
                ragDocuments: [
                    {
                        documentId: 'doc-1',
                        name: 'Document One',
                        source: 's3://bucket/doc1.pdf',
                        similarityScore: 0.87,
                    },
                ],
            },
        };

        renderMessage(message);

        expect(screen.queryByText('0.87')).not.toBeInTheDocument();
    });
});
