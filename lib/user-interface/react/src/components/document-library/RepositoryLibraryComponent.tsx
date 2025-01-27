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

import { ReactElement, useEffect, useState } from 'react';
import { Box, Cards, CollectionPreferences, Header, Pagination, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import {
    CARD_DEFINITIONS,
    DEFAULT_PREFERENCES,
    PAGE_SIZE_OPTIONS,
    VISIBLE_CONTENT_OPTIONS,
} from './DocumentLibraryConfig';
import { useListRagRepositoriesQuery } from '../../shared/reducers/rag.reducer';
import { Repository } from '../types';

export function RepositoryLibraryComponent (): ReactElement {
    const {
        data: allRepos,
        isFetching: fetchingRepos,
    } = useListRagRepositoriesQuery(undefined, { refetchOnMountOrArgChange: 5 });

    const [matchedRepos, setMatchedRepos] = useState<Repository[]>([]);

    const [searchText, setSearchText] = useState<string>('');
    const [numberOfPages, setNumberOfPages] = useState<number>(1);
    const [currentPageIndex, setCurrentPageIndex] = useState<number>(1);
    const [selectedItems, setSelectedItems] = useState([]);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [count, setCount] = useState(0);

    useEffect(() => {
        let newPageCount = 0;
        if (searchText) {
            const filteredRepos = allRepos.filter((repo) => JSON.stringify(repo).toLowerCase().includes(searchText.toLowerCase()));
            setMatchedRepos(
                filteredRepos.slice(preferences.pageSize * (currentPageIndex - 1), preferences.pageSize * currentPageIndex),
            );
            newPageCount = Math.ceil(filteredRepos.length / preferences.pageSize);
            setCount(filteredRepos.length);
        } else {
            setMatchedRepos(allRepos ? allRepos.slice(preferences.pageSize * (currentPageIndex - 1), preferences.pageSize * currentPageIndex) : []);
            newPageCount = Math.ceil(allRepos ? (allRepos.length / preferences.pageSize) : 1);
            setCount(allRepos ? allRepos.length : 0);
        }

        if (newPageCount < numberOfPages) {
            setCurrentPageIndex(1);
        }
        setNumberOfPages(newPageCount);
    }, [allRepos, searchText, preferences, currentPageIndex, numberOfPages]);

    return (
        <>
            <Cards
                onSelectionChange={({ detail }) => setSelectedItems(detail?.selectedItems ?? [])}
                selectedItems={selectedItems}
                ariaLabels={{
                    itemSelectionLabel: (e, t) => `select ${t.modelName}`,
                    selectionGroupLabel: 'Repo selection',
                }}
                cardDefinition={CARD_DEFINITIONS}
                visibleSections={preferences.visibleContent}
                loadingText='Loading repos'
                items={matchedRepos}
                trackBy='repositoryId'
                variant='full-page'
                loading={fetchingRepos}
                cardsPerRow={[{ cards: 3 }]}
                header={
                    <Header counter={`(${count})` ?? ''}>
                        Repositories
                    </Header>
                }
                filter={<TextFilter filteringText={searchText}
                    filteringPlaceholder='Find repos'
                    filteringAriaLabel='Find repos'
                    onChange={({ detail }) => {
                        setSearchText(detail.filteringText);
                    }} />}
                pagination={<Pagination currentPageIndex={currentPageIndex}
                    onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
                    pagesCount={numberOfPages} />}
                preferences={
                    <CollectionPreferences
                        title='Preferences'
                        confirmLabel='Confirm'
                        cancelLabel='Cancel'
                        preferences={preferences}
                        onConfirm={({ detail }) => setPreferences(detail)}
                        pageSizePreference={{
                            title: 'Page size',
                            options: PAGE_SIZE_OPTIONS,
                        }}
                        visibleContentPreference={{
                            title: 'Select visible columns',
                            options: VISIBLE_CONTENT_OPTIONS,
                        }}
                    />
                }
                empty={
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>No repositories</b>
                        </SpaceBetween>
                    </Box>
                }
            />
        </>
    );
}

export default RepositoryLibraryComponent;
