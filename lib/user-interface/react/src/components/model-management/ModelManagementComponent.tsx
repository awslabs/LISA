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

import { useState } from 'react';
import { Box, Cards, CollectionPreferences, Header, Pagination, TextFilter } from '@cloudscape-design/components';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { useGetAllModelsQuery } from '../../shared/reducers/model-management.reducer';
import CreateModelModal from './create-model/CreateModelModal';
import {
    CARD_DEFINITIONS,
    DEFAULT_PREFERENCES,
    PAGE_SIZE_OPTIONS,
    VISIBLE_CONTENT_OPTIONS,
} from './ModelManagementUtils';
import { ModelActions } from './ModelManagementActions';

export function ModelManagementComponent () {
    const { data: allModels, isFetching: fetchingModels } = useGetAllModelsQuery();

    const [selectedItems, setSelectedItems] = useState([]);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [newModelModalVisible, setNewModelModelVisible] = useState(false);
    const [isEdit, setEdit] = useState(false);

    return (
        <>
            <CreateModelModal visible={newModelModalVisible} setVisible={setNewModelModelVisible} isEdit={isEdit} selectedItems={selectedItems}/>
            <Cards
                onSelectionChange={({ detail }) => setSelectedItems(detail?.selectedItems ?? [])}
                selectedItems={selectedItems}
                ariaLabels={{
                    itemSelectionLabel: (e, t) => `select ${t.ModelName}`,
                    selectionGroupLabel: 'Model selection',
                }}
                cardDefinition={CARD_DEFINITIONS}
                visibleSections={preferences.visibleContent}
                loadingText='Loading models'
                items={allModels}
                selectionType='single' // single | multi
                trackBy='ModelId'
                variant='full-page'
                loading={fetchingModels}
                header={
                    <Header
                        counter={selectedItems?.length ? `(${selectedItems.length})` : ''}
                        actions={
                            <ModelActions
                                selectedItems={selectedItems}
                                setSelectedItems={setSelectedItems}
                                setNewModelModelVisible={setNewModelModelVisible}
                                setEdit={setEdit}
                            />
                        }
                    >
                        Models
                    </Header>
                }
                filter={<TextFilter filteringPlaceholder='Find models' />}
                pagination={<Pagination currentPageIndex={1} pagesCount={1} />}
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
