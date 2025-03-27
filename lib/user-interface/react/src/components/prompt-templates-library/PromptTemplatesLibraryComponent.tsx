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

import { Button, Header, Link, Pagination, Select, SelectProps, SpaceBetween, Table, TextContent, TextFilter } from '@cloudscape-design/components';
import 'react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useListPromptTemplatesQuery } from '../../shared/reducers/prompt-templates.reducer';
import {PromptTemplatesActions} from './PromptTemplatesActions';

export function PromptTemplatesLibraryComponent () {
    const navigate = useNavigate();

    const [selectedOption, setSelectedOption] = useState<SelectProps.Option>({label: 'Owned by me', value: ''});
    const args = {showPublic: Boolean(selectedOption.value)};
    const { data: {Items: allItems} = {Items: []}, isFetching } = useListPromptTemplatesQuery(args, {});
    const { paginationProps, filterProps, items, collectionProps, filteredItemsCount, actions } = useCollection(allItems, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'id',
            keepSelection: false
        },
        sorting: {
            defaultState: {
                isDescending: true,
                sortingColumn: {
                    sortingField: 'created'
                }
            }
        },
        filtering: {
            fields: ['title', 'owner'],
        },
        pagination: {
            defaultPage: 1,
            pageSize: 10
        }
    });

    return (
        <Table
            {...collectionProps}
            header={
                <Header counter={filteredItemsCount ? `(${filteredItemsCount})` : undefined} actions={<PromptTemplatesActions
                    selectedItems={collectionProps.selectedItems || []}
                    setSelectedItems={actions.setSelectedItems}
                    showPublic={args.showPublic}
                />}>
                    Prompt Templates
                </Header>
            }
            sortingDisabled={false}
            selectionType='single'
            selectedItems={collectionProps.selectedItems}
            loading={isFetching}
            loadingText='Loading Prompt Templates'
            empty={(
                <SpaceBetween direction='vertical' size='s' alignItems='center'>
                    <TextContent><small>No Prompt Templates found.</small></TextContent>
                    <Button variant='inline-link' onClick={() => navigate('./new')}>Create Prompt Template</Button>
                </SpaceBetween>
            )}
            variant='full-page'
            filter={<SpaceBetween direction='horizontal' size='s'>
                <TextFilter filteringPlaceholder='Search by title' {...filterProps} disabled={isFetching}></TextFilter>
                <Select selectedOption={selectedOption} options={[
                    {label: 'Owned by me', value: ''},
                    {label: 'Public', value: 'true'}
                ]} onChange={({detail}) => {
                    setSelectedOption(detail.selectedOption);
                }} />
            </SpaceBetween>}
            pagination={<Pagination {...paginationProps} />}
            items={items}
            columnDefinitions={[
                { header: 'Title', cell: (item) => <Link onClick={() => navigate(`./${item.id}`)}>{item.title}</Link>},
                { header: 'Groups', cell: (item) => {
                    if (item.groups.findIndex((group) => group === 'lisa:public') > -1) {
                        return <em>(public)</em>;
                    }

                    return item.groups.length ? item.groups.map((group) => group.replace(/^\w+?:/, '')).join(', ') : '-';
                }},
                { header: 'Updated', cell: (item) => item.created, id: 'created', sortingField: 'created'},
                { header: 'Revision', cell: (item) => (item.revision || 1)}
            ]}
        />
    );
}

export default PromptTemplatesLibraryComponent;
