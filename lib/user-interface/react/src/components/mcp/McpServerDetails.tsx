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

import {
    Grid,
    Header,
    Pagination,
    SpaceBetween,
    Table,
    TextContent
} from '@cloudscape-design/components';
import 'react';
import React from 'react';
import { useParams } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLazyGetMcpServerQuery } from '@/shared/reducers/mcp-server.reducer';
import { useMcp } from 'use-mcp/react';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Box from '@cloudscape-design/components/box';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useAppDispatch } from '@/config/store';

export function McpServerDetails () {
    const { mcpServerId } = useParams();
    const dispatch = useAppDispatch();
    const [getMcpServerQuery, {isUninitialized, data, isFetching, isSuccess}] = useLazyGetMcpServerQuery();

    if (isSuccess) {
        dispatch(setBreadcrumbs([
            { text: 'MCP Servers', href: '/mcp-connections' },
            { text: data.name, href: '' }
        ]));
    }

    if (isUninitialized && mcpServerId) {
        getMcpServerQuery(mcpServerId);
    }

    const {
        state,          // Connection state: 'discovering' | 'authenticating' | 'connecting' | 'loading' | 'ready' | 'failed'
        tools,          // Available tools from MCP server
    } = useMcp({
        url: data?.url ?? ' ',
        clientName: data?.name,
        autoReconnect: true,
        clientConfig: data?.clientConfig ?? undefined,
        customHeaders: data?.customHeaders ?? undefined,
    });

    const { paginationProps, items, collectionProps } = useCollection(tools, {
        selection: {
            defaultSelectedItems: [],
            trackBy: 'name',
            keepSelection: false
        },
        pagination: {
            defaultPage: 1,
            pageSize: 20
        }
    });

    return (
        <Table
            {...collectionProps}
            header={
                <Grid gridDefinition={[{ colspan:6 }, { colspan:6 }]}>
                    <Header counter={`(${tools.length.toString() ?? undefined})`}>
                        {data?.name} Tool Details

                    </Header>
                    <Box float='right' variant='div'>
                        <StatusIndicator type={state === 'ready' ? 'success' : state.endsWith('ing') ? 'pending' : 'error'}>
                            {state === 'ready' ? 'Connected' : state.endsWith('ing') ? 'Pending' : 'Error'}
                        </StatusIndicator>
                    </Box>
                </Grid>
            }
            sortingDisabled={false}
            selectedItems={collectionProps.selectedItems}
            loading={isFetching || state === 'connecting'}
            loadingText='Loading Server Tools'
            empty={(
                <SpaceBetween direction='vertical' size='s' alignItems='center'>
                    <TextContent><small>Tools not found.</small></TextContent>
                </SpaceBetween>
            )}
            variant='full-page'
            pagination={<Pagination {...paginationProps} />}
            items={items}
            columnDefinitions={[
                { header: 'Name', cell: (item) => item.name},
                { header: 'Description', cell: (item) => item.description},
            ]}
        />
    );
}

export default McpServerDetails;
