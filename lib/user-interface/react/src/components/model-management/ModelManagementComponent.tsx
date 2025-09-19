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
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import CreateModelModal from './create-model/CreateModelModal';
import {
    createCardDefinitions,
    DEFAULT_PREFERENCES,
    PAGE_SIZE_OPTIONS,
    VISIBLE_CONTENT_OPTIONS,
} from './ModelManagementUtils';
import { ModelActions } from './ModelManagementActions';
import { IModel, ModelStatus } from '../../shared/model/model-management.model';
import { useLocalStorage } from '../../shared/hooks/use-local-storage';
import { useGetConfigurationQuery, useUpdateConfigurationMutation } from '@/shared/reducers/configuration.reducer';

export function ModelManagementComponent (): ReactElement {
    const [shouldPoll, setShouldPoll] = useState(true);
    const { data: allModels, isFetching: fetchingModels, refetch } = useGetAllModelsQuery(undefined, {
        refetchOnMountOrArgChange: true,
        refetchOnFocus: false, // Prevent unnecessary refetches
        pollingInterval: shouldPoll ? 30000 : undefined // 30 seconds in milliseconds
    });
    const [matchedModels, setMatchedModels] = useState<IModel[]>([]);
    const [searchText, setSearchText] = useState<string>('');
    const [numberOfPages, setNumberOfPages] = useState<number>(1);
    const [currentPageIndex, setCurrentPageIndex] = useState<number>(1);

    const [selectedItems, setSelectedItems] = useState([]);
    const [preferences, setPreferences] = useLocalStorage('ModelManagerPreferences', DEFAULT_PREFERENCES);
    const [newModelModalVisible, setNewModelModelVisible] = useState(false);
    const [isEdit, setEdit] = useState(false);
    const [count, setCount] = useState('');

    const {
        data: config,
    } = useGetConfigurationQuery('global', { refetchOnMountOrArgChange: true });
    const [updateConfigMutation] = useUpdateConfigurationMutation();

    // Ensure models are fetched on component mount
    useEffect(() => {
        // Force refetch on mount if no data is available
        if (!allModels && !fetchingModels) {
            console.log('No models data available, triggering refetch...');
            refetch();
        }
    }, [allModels, fetchingModels, refetch]);

    useEffect(() => {
        const finalStatePredicate = (model: IModel) => [ModelStatus.InService, ModelStatus.Failed, ModelStatus.Stopped].includes(model.status);
        if (allModels?.every(finalStatePredicate)) {
            setShouldPoll(false);
        }
    }, [allModels, setShouldPoll]);

    useEffect(() => {
        let newPageCount = 0;
        if (searchText) {
            const filteredModels = allModels.filter((model) => JSON.stringify(model).toLowerCase().includes(searchText.toLowerCase()));
            setMatchedModels(filteredModels.slice(preferences.pageSize * (currentPageIndex - 1), preferences.pageSize * currentPageIndex));
            newPageCount = Math.ceil(filteredModels.length / preferences.pageSize);
            setCount(filteredModels.length.toString());
        } else {
            setMatchedModels(allModels ? allModels.slice(preferences.pageSize * (currentPageIndex - 1), preferences.pageSize * currentPageIndex) : []);
            newPageCount = Math.ceil(allModels ? (allModels.length / preferences.pageSize) : 1);
            setCount(allModels ? allModels.length.toString() : '0');
        }

        if (newPageCount < numberOfPages) {
            setCurrentPageIndex(1);
        }
        setNumberOfPages(newPageCount);
    }, [allModels, searchText, preferences, currentPageIndex, numberOfPages]);

    return (
        <>
            <CreateModelModal visible={newModelModalVisible} setVisible={setNewModelModelVisible} isEdit={isEdit} setIsEdit={setEdit} selectedItems={selectedItems} setSelectedItems={setSelectedItems} />
            <Cards
                onSelectionChange={({ detail }) => setSelectedItems(detail?.selectedItems ?? [])}
                selectedItems={selectedItems}
                ariaLabels={{
                    itemSelectionLabel: (_, t) => `select ${t.modelName}`,
                    selectionGroupLabel: 'Model selection',
                }}
                cardDefinition={createCardDefinitions(config?.[0]?.configuration?.global?.defaultModel)}
                visibleSections={preferences.visibleContent}
                loadingText='Loading models'
                items={matchedModels}
                selectionType='single' // single | multi
                trackBy='modelId'
                variant='full-page'
                loading={fetchingModels}
                cardsPerRow={[{ cards: 3 }]}
                header={
                    <Header
                        counter={`(${count})`}
                        actions={
                            <ModelActions
                                selectedItems={selectedItems}
                                setSelectedItems={setSelectedItems}
                                setNewModelModelVisible={setNewModelModelVisible}
                                setEdit={setEdit}
                                updateConfigMutation={updateConfigMutation}
                                currentDefaultModel={config?.[0]?.configuration?.global?.defaultModel}
                                currentConfig={config}
                                refetch={refetch}
                            />
                        }
                    >
                        Models
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
        </>
    );
}

export default ModelManagementComponent;
