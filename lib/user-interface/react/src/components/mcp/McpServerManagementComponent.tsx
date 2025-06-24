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

import { Button, Header, Link, Pagination, SpaceBetween, Table, TextContent } from '@cloudscape-design/components';
import 'react';
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import {McpServerActions} from './McpServerActions';
import { useListMcpServersQuery } from '@/shared/reducers/mcp-server.reducer';

export function McpServerManagementComponent () {
    const navigate = useNavigate();

    const { data: {Items: allItems} = {Items: []}, isFetching } = useListMcpServersQuery(undefined, {});
    const { paginationProps, items, collectionProps, filteredItemsCount, actions } = useCollection(allItems, {
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
            fields: ['name', 'owner'],
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
                <Header counter={filteredItemsCount ? `(${filteredItemsCount})` : undefined} actions={<McpServerActions
                    selectedItems={collectionProps.selectedItems || []}
                    setSelectedItems={actions.setSelectedItems}
                />}>
                    MCP Connections
                </Header>
            }
            sortingDisabled={false}
            selectionType='single'
            selectedItems={collectionProps.selectedItems}
            loading={isFetching}
            loadingText='Loading MCP Connections'
            empty={(
                <SpaceBetween direction='vertical' size='s' alignItems='center'>
                    <TextContent><small>No MCP Connections found.</small></TextContent>
                    <Button variant='inline-link' onClick={() => navigate('./new')}>Create MCP Connection</Button>
                </SpaceBetween>
            )}
            variant='full-page'
            pagination={<Pagination {...paginationProps} />}
            items={items}
            columnDefinitions={[
                { header: 'Name', cell: (item) => <Link onClick={() => navigate(`./${item.id}`)}>{item.name}</Link>},
                { header: 'URL', cell: (item) => item.url, id: 'url', sortingField: 'url'},
                { header: 'Owner', cell: (item) => item.owner, id: 'owner', sortingField: 'owner'},
                { header: 'Updated', cell: (item) => item.created, id: 'created', sortingField: 'created'},
            ]}
        />
    );
}

export default McpServerManagementComponent;
