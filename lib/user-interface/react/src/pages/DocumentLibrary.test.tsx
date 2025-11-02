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

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { DocumentLibrary } from './DocumentLibrary';
import { renderWithProviders } from '../test/helpers/render';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

// Mock DocumentLibraryComponent
const mockDocumentLibraryComponent = vi.fn();
vi.mock('../components/document-library/DocumentLibraryComponent', () => ({
    default: (props: any) => {
        mockDocumentLibraryComponent(props);
        return (
            <div data-testid="document-library-component">
                <div data-testid="repository-id">{props.repositoryId}</div>
                <div data-testid="collection-id">{props.collectionId || 'none'}</div>
            </div>
        );
    },
}));

describe('DocumentLibrary with optional collectionId', () => {
    it('should accept repositoryId parameter from route', () => {
        const setNav = vi.fn();
        
        renderWithProviders(
            <MemoryRouter initialEntries={['/document-library/test-repo-1']}>
                <Routes>
                    <Route path="/document-library/:repoId/:collectionId?" element={<DocumentLibrary setNav={setNav} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByTestId('repository-id')).toHaveTextContent('test-repo-1');
    });

    it('should accept optional collectionId parameter from route', () => {
        const setNav = vi.fn();
        
        renderWithProviders(
            <MemoryRouter initialEntries={['/document-library/test-repo-1/test-collection-1']}>
                <Routes>
                    <Route path="/document-library/:repoId/:collectionId?" element={<DocumentLibrary setNav={setNav} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByTestId('repository-id')).toHaveTextContent('test-repo-1');
        expect(screen.getByTestId('collection-id')).toHaveTextContent('test-collection-1');
    });

    it('should pass collectionId to DocumentLibraryComponent when provided', () => {
        const setNav = vi.fn();
        
        renderWithProviders(
            <MemoryRouter initialEntries={['/document-library/test-repo-1/test-collection-1']}>
                <Routes>
                    <Route path="/document-library/:repoId/:collectionId?" element={<DocumentLibrary setNav={setNav} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(mockDocumentLibraryComponent).toHaveBeenCalledWith(
            expect.objectContaining({
                repositoryId: 'test-repo-1',
                collectionId: 'test-collection-1',
            })
        );
    });

    it('should work without collectionId (backward compatibility)', () => {
        const setNav = vi.fn();
        
        renderWithProviders(
            <MemoryRouter initialEntries={['/document-library/test-repo-1']}>
                <Routes>
                    <Route path="/document-library/:repoId/:collectionId?" element={<DocumentLibrary setNav={setNav} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByTestId('repository-id')).toHaveTextContent('test-repo-1');
        expect(screen.getByTestId('collection-id')).toHaveTextContent('none');
    });

    it('should set navigation to null on mount', () => {
        const setNav = vi.fn();
        
        renderWithProviders(
            <MemoryRouter initialEntries={['/document-library/test-repo-1']}>
                <Routes>
                    <Route path="/document-library/:repoId/:collectionId?" element={<DocumentLibrary setNav={setNav} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(setNav).toHaveBeenCalledWith(null);
    });
});
