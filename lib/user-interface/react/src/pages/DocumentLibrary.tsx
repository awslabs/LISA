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

import { ReactElement, useEffect } from 'react';
import DocumentLibraryComponent from '../components/document-library/DocumentLibraryComponent';
import { useParams } from 'react-router-dom';
import { useGetCollectionQuery } from '@/shared/reducers/rag.reducer';
import { useAppDispatch } from '@/config/store';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';

export function DocumentLibrary ({ setNav }): ReactElement {
    const { repoId, collectionId } = useParams();
    const dispatch = useAppDispatch();

    // Fetch collection data to get the collection name
    const { data: collectionData } = useGetCollectionQuery(
        { repositoryId: repoId, collectionId },
        { skip: !repoId || !collectionId }
    );

    useEffect(() => {
        setNav(null);
    }, [setNav]);

    // Update breadcrumbs when collection data is available
    useEffect(() => {
        if (repoId && collectionId && collectionData) {
            dispatch(setBreadcrumbs([
                { text: 'Document Library', href: '/document-library' },
                { text: repoId, href: `/document-library/${repoId}` },
                { text: collectionData.name, href: `/document-library/${repoId}/${collectionId}` },
            ]));
        } else if (repoId) {
            dispatch(setBreadcrumbs([
                { text: 'Document Library', href: '/document-library' },
                { text: repoId, href: `/document-library/${repoId}` },
            ]));
        }
    }, [repoId, collectionId, collectionData, dispatch]);

    return <DocumentLibraryComponent repositoryId={repoId} collectionId={collectionId} />;
}

export default DocumentLibrary;
