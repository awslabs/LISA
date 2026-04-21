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

import { ReactElement, useState } from 'react';
import {
    Box,
    Table,
    Header,
    SpaceBetween,
    Pagination,
    TextFilter,
    CollectionPreferences,
    Badge,
} from '@cloudscape-design/components';
import { useListTokensQuery } from '../../shared/reducers/api-token.reducer';
import { ITokenInfo, ICreateTokenResponse } from '../../shared/model/api-token.model';
import { CreateTokenWizard } from './CreateTokenWizard';
import { CreateUserTokenWizard } from './CreateUserTokenWizard';
import { TokenDisplayModal } from './TokenDisplayModal';
import { ApiTokenActions } from './ApiTokenActions';
import { useLocalStorage } from '../../shared/hooks/use-local-storage';
import { useAppSelector } from '../../config/store';
import { selectCurrentUsername } from '../../shared/reducers/user.reducer';
import { formatDate } from '../../shared/util/formats';

const DEFAULT_PREFERENCES = {
    pageSize: 10,
    visibleContent: ['name', 'username', 'createdBy', 'createdDate', 'expiration', 'status', 'groups', 'systemToken'],
};

const PAGE_SIZE_OPTIONS = [
    { value: 10, label: '10 tokens' },
    { value: 20, label: '20 tokens' },
    { value: 50, label: '50 tokens' },
];

const VISIBLE_CONTENT_OPTIONS = [
    {
        label: 'Token Properties',
        options: [
            { id: 'name', label: 'Token name' },
            { id: 'username', label: 'Created for' },
            { id: 'createdBy', label: 'Username' },
            { id: 'createdDate', label: 'Created date' },
            { id: 'expiration', label: 'Expiration' },
            { id: 'status', label: 'Status' },
            { id: 'groups', label: 'Groups' },
            { id: 'systemToken', label: 'System token' },
            { id: 'tokenUUID', label: 'Token UUID' },
        ],
    },
];

export type ApiTokenManagementComponentProps = {
    currentUserOnly?: boolean;
};

export function ApiTokenManagementComponent ({ currentUserOnly = false }: ApiTokenManagementComponentProps): ReactElement {
    const currentUsername = useAppSelector(selectCurrentUsername);
    const { data: allTokens, isFetching, refetch } = useListTokensQuery(undefined, {
        refetchOnMountOrArgChange: true,
        pollingInterval: 300000, // Refresh every 5 minutes
    });

    const [selectedItems, setSelectedItems] = useState<ITokenInfo[]>([]);
    const [createWizardVisible, setCreateWizardVisible] = useState(false);
    const [tokenDisplayVisible, setTokenDisplayVisible] = useState(false);
    const [createdToken, setCreatedToken] = useState<ICreateTokenResponse | null>(null);
    const [filterText, setFilterText] = useState('');
    const [currentPageIndex, setCurrentPageIndex] = useState(1);
    const [preferences, setPreferences] = useLocalStorage('ApiTokenManagementPreferences', DEFAULT_PREFERENCES);

    const handleTokenCreated = (token: ICreateTokenResponse) => {
        setCreatedToken(token);
        setTokenDisplayVisible(true);
        refetch();
    };

    const handleTokenDisplayDismiss = () => {
        setTokenDisplayVisible(false);
        setCreatedToken(null);
    };

    // Check if current user already has a token (for disabling create button)
    const userHasToken = currentUserOnly && allTokens ?
        allTokens.some((token) => token.username === currentUsername) : false;

    // Filter tokens: first by current user if needed, then by search text
    const filteredTokens = allTokens?.filter((token) => {
        // Filter to current user only if requested
        if (currentUserOnly && token.username !== currentUsername) {
            return false;
        }

        // Then apply search filter
        if (!filterText) return true;
        const searchLower = filterText.toLowerCase();
        return (
            token.name.toLowerCase().includes(searchLower) ||
            token.username.toLowerCase().includes(searchLower) ||
            token.createdBy.toLowerCase().includes(searchLower) ||
            token.groups.some((g) => g.toLowerCase().includes(searchLower))
        );
    }) || [];

    // Calculate pagination
    const totalPages = Math.ceil(filteredTokens.length / preferences.pageSize);

    // Clamp current page to valid range
    const validPageIndex = totalPages > 0 && currentPageIndex > totalPages ? 1 : currentPageIndex;

    // Paginate filtered tokens
    const startIndex = (validPageIndex - 1) * preferences.pageSize;
    const paginatedTokens = filteredTokens.slice(startIndex, startIndex + preferences.pageSize);

    return (
        <>
            {currentUserOnly ? (
                <CreateUserTokenWizard
                    visible={createWizardVisible}
                    setVisible={setCreateWizardVisible}
                    onTokenCreated={handleTokenCreated}
                />
            ) : (
                <CreateTokenWizard
                    visible={createWizardVisible}
                    setVisible={setCreateWizardVisible}
                    onTokenCreated={handleTokenCreated}
                />
            )}
            <TokenDisplayModal
                visible={tokenDisplayVisible}
                token={createdToken}
                onDismiss={handleTokenDisplayDismiss}
            />
            <Table
                onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
                selectedItems={selectedItems}
                ariaLabels={{
                    selectionGroupLabel: 'Items selection',
                    allItemsSelectionLabel: () => 'select all',
                    itemSelectionLabel: (_selectedItem, item) => item.name,
                }}
                columnDefinitions={[
                    {
                        id: 'name',
                        header: 'Token name',
                        cell: (item) => item.name,
                        sortingField: 'name',
                    },
                    {
                        id: 'username',
                        header: 'Username',
                        cell: (item) => item.username,
                        sortingField: 'username',
                    },
                    {
                        id: 'createdBy',
                        header: 'Created by',
                        cell: (item) => item.createdBy,
                        sortingField: 'createdBy',
                    },
                    {
                        id: 'createdDate',
                        header: 'Created date',
                        cell: (item) => formatDate(item.createdDate * 1000),
                        sortingField: 'createdDate',
                    },
                    {
                        id: 'expiration',
                        header: 'Expiration',
                        cell: (item) => formatDate(item.tokenExpiration * 1000),
                        sortingField: 'tokenExpiration',
                    },
                    {
                        id: 'status',
                        header: 'Status',
                        cell: (item) => (
                            item.isLegacy ? (
                                <Badge color='red'>Legacy</Badge>
                            ) : (
                                <Badge color={item.isExpired ? 'red' : 'green'}>
                                    {item.isExpired ? 'Expired' : 'Active'}
                                </Badge>
                            )
                        ),
                    },
                    {
                        id: 'groups',
                        header: 'Groups',
                        cell: (item) => (
                            <SpaceBetween direction='horizontal' size='xxs'>
                                {item.groups.length > 0 ? (
                                    item.groups.map((group) => (
                                        <Badge key={group}>{group}</Badge>
                                    ))
                                ) : (
                                    <span>—</span>
                                )}
                            </SpaceBetween>
                        ),
                    },
                    {
                        id: 'systemToken',
                        header: 'System token',
                        cell: (item) => (
                            item.isSystemToken ? <Badge>System</Badge> : <span>—</span>
                        ),
                    },
                    {
                        id: 'tokenUUID',
                        header: 'Token UUID',
                        cell: (item) => (
                            <code style={{ fontSize: '12px' }}>{item.tokenUUID}</code>
                        ),
                        sortingField: 'tokenUUID',
                    },
                ]}
                visibleColumns={preferences.visibleContent}
                items={paginatedTokens}
                loading={isFetching}
                loadingText='Loading tokens'
                resizableColumns
                selectionType='single'
                trackBy='name'
                variant='full-page'
                empty={
                    <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
                        <SpaceBetween size='m'>
                            <b>No API tokens</b>
                            <span>No tokens have been created yet.</span>
                        </SpaceBetween>
                    </Box>
                }
                filter={
                    <TextFilter
                        filteringText={filterText}
                        filteringPlaceholder='Find tokens'
                        filteringAriaLabel='Filter tokens'
                        onChange={({ detail }) => setFilterText(detail.filteringText)}
                    />
                }
                header={
                    <Header
                        counter={`(${filteredTokens.length})`}
                        actions={
                            <ApiTokenActions
                                selectedItems={selectedItems}
                                setSelectedItems={setSelectedItems}
                                setCreateWizardVisible={setCreateWizardVisible}
                                onRefresh={refetch}
                                disableCreate={userHasToken}
                                isFetching={isFetching}
                            />
                        }
                    >
                        API Tokens
                    </Header>
                }
                pagination={
                    <Pagination
                        currentPageIndex={validPageIndex}
                        onChange={({ detail }) => setCurrentPageIndex(detail.currentPageIndex)}
                        pagesCount={totalPages}
                    />
                }
                preferences={
                    <CollectionPreferences
                        title='Preferences'
                        confirmLabel='Confirm'
                        cancelLabel='Cancel'
                        preferences={preferences}
                        onConfirm={({ detail }) => {
                            if (detail.pageSize && detail.visibleContent) {
                                setPreferences({
                                    pageSize: detail.pageSize,
                                    visibleContent: [...detail.visibleContent],
                                });
                            }
                        }}
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
            />
        </>
    );
}

export default ApiTokenManagementComponent;
