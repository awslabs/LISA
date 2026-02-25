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

import { useCallback, useState } from 'react';

export interface DocumentForPanel {
    documentId: string;
    repositoryId: string;
    name: string;
    source: string;
}

export interface UseDocumentSidePanelReturn {
    showDocSidePanel: boolean;
    selectedDocumentForPanel: DocumentForPanel | null;
    handleOpenDocument: (document: DocumentForPanel) => void;
    handleCloseDocPanel: () => void;
}

/**
 * Custom hook to manage the document side panel state and handlers.
 * Provides consistent functionality for opening and closing the document viewer.
 * 
 * @returns Object containing panel state and handler functions
 */
export function useDocumentSidePanel(): UseDocumentSidePanelReturn {
    const [showDocSidePanel, setShowDocSidePanel] = useState(false);
    const [selectedDocumentForPanel, setSelectedDocumentForPanel] = useState<DocumentForPanel | null>(null);

    // Handler to open document in side panel
    const handleOpenDocument = useCallback((document: DocumentForPanel) => {
        setSelectedDocumentForPanel(document);
        setShowDocSidePanel(true);
    }, []);

    // Handler to close document side panel
    const handleCloseDocPanel = useCallback(() => {
        setShowDocSidePanel(false);
        setSelectedDocumentForPanel(null);
    }, []);

    return {
        showDocSidePanel,
        selectedDocumentForPanel,
        handleOpenDocument,
        handleCloseDocPanel,
    };
}