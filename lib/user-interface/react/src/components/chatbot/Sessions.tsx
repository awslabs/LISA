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

import Table from '@cloudscape-design/components/table';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Link from '@cloudscape-design/components/link';
import Header from '@cloudscape-design/components/header';
import { Pagination } from '@cloudscape-design/components';
import Button from '@cloudscape-design/components/button';
import { DateTime } from 'luxon';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { v4 as uuidv4 } from 'uuid';
import { useGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';
import {
    sessionApi,
    useDeleteAllSessionsForUserMutation,
    useDeleteSessionByIdMutation,
    useListSessionsQuery
} from '../../shared/reducers/session.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { useEffect, useState } from 'react';

export function Sessions () {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const [selectedItems, setSelectedItems] = useState([]);
    const [deleteById, { isSuccess: isDeleteByIdSuccess, isError: isDeleteByIdError, error: deleteByIdError, isLoading: isDeleteByIdLoading },] = useDeleteSessionByIdMutation();
    const [deleteUserSessions, { isSuccess: isDeleteUserSessionsSuccess, isError: isDeleteUserSessionsError, error: deleteUserSessionsError, isLoading: isDeleteUserSessionsLoading },] = useDeleteAllSessionsForUserMutation();
    const { data: config } = useGetConfigurationQuery('global', {refetchOnMountOrArgChange: 5});
    const { data: sessions, isLoading } = useListSessionsQuery(null, {refetchOnMountOrArgChange: 5});
    const { items, collectionProps, paginationProps } = useCollection(sessions ?? [], {
        filtering: {
            empty: (
                <Box margin={{ vertical: 'xs' }} textAlign='center'>
                    <SpaceBetween size='m'>
                        <b>No history</b>
                    </SpaceBetween>
                </Box>
            ),
        },
        pagination: { pageSize: 20 },
        sorting: {
            defaultState: {
                sortingColumn: {
                    sortingField: 'StartTime',
                },
                isDescending: true,
            },
        },
        selection: {},
    });

    useEffect(() => {
        if (!isDeleteByIdLoading && isDeleteByIdSuccess) {
            notificationService.generateNotification('Successfully deleted session', 'success');
        } else if (!isDeleteByIdLoading && isDeleteByIdError) {
            notificationService.generateNotification(`Error deleting session: ${deleteByIdError.data?.message ?? deleteByIdError.data}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteByIdSuccess, isDeleteByIdError, deleteByIdError, isDeleteByIdLoading]);

    useEffect(() => {
        if (!isDeleteUserSessionsLoading && isDeleteUserSessionsSuccess) {
            notificationService.generateNotification('Successfully deleted all user sessions', 'success');
        } else if (!isDeleteUserSessionsLoading && isDeleteUserSessionsError) {
            notificationService.generateNotification(`Error deleting user sessions: ${deleteUserSessionsError.data?.message ?? deleteUserSessionsError.data}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteUserSessionsSuccess, isDeleteUserSessionsError, deleteUserSessionsError, isDeleteUserSessionsLoading]);

    return (
        <div className='p-5'>
            <Table
                {...collectionProps}
                variant='embedded'
                items={items}
                pagination={<Pagination {...paginationProps} />}
                loadingText='Loading history'
                loading={isLoading || isDeleteByIdLoading || isDeleteUserSessionsLoading}
                selectedItems={selectedItems}
                onSelectionChange={({ detail }) =>
                    setSelectedItems(detail.selectedItems)
                }
                resizableColumns
                sortingDescending={true}
                selectionType='multi'
                columnDefinitions={[
                    {
                        id: 'title',
                        header: 'Title',
                        cell: (e) => <Link variant='primary' href={`#/chatbot/${e.sessionId}`}>{e.history[0].content || 'No Content'}</Link>,
                        sortingField: 'title',
                        isRowHeader: true,
                    },
                    {
                        id: 'StartTime',
                        header: 'Time',
                        cell: (e) => DateTime.fromISO(new Date(e.startTime).toISOString()).toLocaleString(DateTime.DATETIME_SHORT),
                        sortingField: 'StartTime',
                        sortingComparator: (a, b) => {
                            return new Date(b.startTime).getTime() - new Date(a.startTime).getTime();
                        },
                    },
                ]}
                header={
                    <Header
                        actions={
                            <div className='mr-10'>
                                <SpaceBetween direction='horizontal' size='m'>
                                    <Button iconName='add-plus' variant='inline-link'>
                                        <Link href={`/#/chatbotv2/${uuidv4()}`}>New</Link>
                                    </Button>
                                    <Button
                                        iconAlt='Refresh list'
                                        iconName='refresh'
                                        variant='inline-link'
                                        onClick={() => dispatch(sessionApi.util.invalidateTags(['sessions']))}
                                    >
                                        Refresh
                                    </Button>
                                    {config && config[0].configuration.enabledComponents.deleteSessionHistory &&
                                    <Button
                                        iconAlt='Delete session(s)'
                                        iconName='delete-marker'
                                        variant='inline-link'
                                        onClick={() => {
                                            if (selectedItems && selectedItems.length === 1) {
                                                setSelectedItems([]);
                                                deleteById(selectedItems[0].sessionId);
                                            } else {
                                                deleteUserSessions();
                                            }
                                        }}
                                        disabled={selectedItems.length > 1 && (selectedItems.length > 1 && selectedItems.length !== items.length)}
                                    >
                                        {selectedItems && selectedItems.length === 1 ? 'Delete one' : 'Delete all'}
                                    </Button>}
                                </SpaceBetween>
                            </div>
                        }
                    >
                        History
                    </Header>
                }
            />
        </div>
    );
}
export default Sessions;
