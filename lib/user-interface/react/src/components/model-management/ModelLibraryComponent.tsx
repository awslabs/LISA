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

import { ReactElement, useEffect, useMemo, useState } from 'react';
import { Box, Cards, CollectionPreferences, Header, Pagination, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import {
    CARD_DEFINITIONS,
    DEFAULT_PREFERENCES,
    PAGE_SIZE_OPTIONS,
    VISIBLE_CONTENT_OPTIONS,
} from './ModelManagementUtils';
import { IModel, ModelStatus } from '../../shared/model/model-management.model';
import { useLocalStorage } from '../../shared/hooks/use-local-storage';
import { Duration } from 'luxon';
import { ModelLibraryActions } from './ModelLibraryActions';

export function ModelLibraryComponent () : ReactElement {
    const [shouldPoll, setShouldPoll] = useState(true);
    const { data: allModels, isFetching: fetchingModels } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: true,
        pollingInterval: shouldPoll ? Duration.fromObject({seconds: 30}) : undefined
    });
    const [matchedModels, setMatchedModels] = useState<IModel[]>([]);
    const [searchText, setSearchText] = useState<string>('');
    const [numberOfPages, setNumberOfPages] = useState<number>(1);
    const [currentPageIndex, setCurrentPageIndex] = useState<number>(1);

    const [preferences, setPreferences] = useLocalStorage('ModelLibraryPreferences', DEFAULT_PREFERENCES);
    const [count, setCount] = useState('');

    // Check if polling should stop and update state accordingly
    useEffect(() => {
        const finalStatePredicate = (model) => [ModelStatus.InService, ModelStatus.Failed, ModelStatus.Stopped].includes(model.status);
        if (allModels?.every(finalStatePredicate)) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setShouldPoll(false);
        }
    }, [allModels]);

    // Derive filtered models and pagination data using useMemo
    const { paginatedModels, totalCount, pageCount } = useMemo(() => {
        if (!allModels) {
            return {
                filteredModels: [],
                paginatedModels: [],
                totalCount: 0,
                pageCount: 1
            };
        }

        const filtered = searchText
            ? allModels.filter((model) => JSON.stringify(model).toLowerCase().includes(searchText.toLowerCase()))
            : allModels;

        const startIndex = preferences.pageSize * (currentPageIndex - 1);
        const endIndex = startIndex + preferences.pageSize;
        const paginated = filtered.slice(startIndex, endIndex);
        const calculatedPageCount = Math.ceil(filtered.length / preferences.pageSize) || 1;

        return {
            paginatedModels: paginated,
            totalCount: filtered.length,
            pageCount: calculatedPageCount
        };
    }, [allModels, searchText, preferences.pageSize, currentPageIndex]);

    // Update state based on derived values
    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setMatchedModels(paginatedModels);

        setCount(totalCount.toString());

        if (pageCount < numberOfPages && currentPageIndex > pageCount) {

            setCurrentPageIndex(1);
        }

        setNumberOfPages(pageCount);
    }, [paginatedModels, totalCount, pageCount, numberOfPages, currentPageIndex]);

    return (
        <Cards
            cardDefinition={CARD_DEFINITIONS}
            visibleSections={preferences.visibleContent}
            loadingText='Loading models'
            items={matchedModels}
            trackBy='modelId'
            variant='full-page'
            loading={fetchingModels}
            cardsPerRow={[{ cards: 3 }]}
            header={
                <Header
                    counter={`(${count})`}
                    actions={<ModelLibraryActions />}
                >
                    Model Library
                </Header>
            }
            filter={<TextFilter filteringText={searchText}
                filteringPlaceholder='Find models'
                filteringAriaLabel='Find models'
                onChange={({ detail }) => {
                    setSearchText(detail.filteringText);
                }} />}
            pagination={<Pagination currentPageIndex={currentPageIndex} onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)} pagesCount={numberOfPages} />}
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
                        <b>No models</b>
                    </SpaceBetween>
                </Box>
            }
        />
    );
}

export default ModelLibraryComponent;
