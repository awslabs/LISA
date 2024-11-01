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

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';
import Table from '@cloudscape-design/components/table';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Header from '@cloudscape-design/components/header';
import { Pagination } from '@cloudscape-design/components';
import Button from '@cloudscape-design/components/button';
import { DateTime } from 'luxon';
import { Link } from 'react-router-dom';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { v4 as uuidv4 } from 'uuid';
import { LisaChatSession } from '../types';
import { listSessions, deleteSession, deleteUserSessions } from '../utils';
import { useGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';

export function Sessions () {
    const { data: config } = useGetConfigurationQuery('global', {refetchOnMountOrArgChange: 5});
    const auth = useAuth();
    const [sessions, setSessions] = useState<LisaChatSession[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const { items, collectionProps, paginationProps } = useCollection(sessions, {
        filtering: {
            empty: (
                <Box margin={{ vertical: 'xs' }} textAlign='center' color='inherit'>
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
        doListSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const doListSessions = useCallback(async () => {
        setIsLoading(true);
        const sessions = await listSessions(auth.user?.id_token);
        setSessions(sessions || []);
        setIsLoading(false);
    }, [auth.user?.id_token]);

    const doDeleteSession = async (sessionId) => {
        const status = await deleteSession(sessionId, auth.user?.id_token);
        void status;
        doListSessions();
    };

    const doDeleteUserSessions = async () => {
        const status = await deleteUserSessions(auth.user?.id_token);
        void status;
        doListSessions();
    };

    return (
        <div className='p-5'>
            <Table
                {...collectionProps}
                variant='embedded'
                items={items}
                pagination={<Pagination {...paginationProps} />}
                loadingText='Loading history'
                loading={isLoading}
                resizableColumns
                sortingDescending={true}
                columnDefinitions={[
                    {
                        id: 'title',
                        header: 'Title',
                        cell: (e) => <Link to={`/chatbot/${e.sessionId}`}>{e.history[0].content || 'No Content'}</Link>,
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
                    {
                        id: 'actions',
                        header: 'Actions',
                        cell: (item) => (
                            <SpaceBetween direction='horizontal' size='m'>
                                <Button variant='inline-link'>
                                    <Link to={`/chatbot/${item.sessionId}`}>Open</Link>
                                </Button>
                                {config && config[0]?.configuration.enabledComponents.deleteSessionHistory &&
                                <Button variant='inline-link' onClick={() => doDeleteSession(item.sessionId)}>
                                    Delete
                                </Button>}
                            </SpaceBetween>
                        ),
                        minWidth: 170,
                    },
                ]}
                header={
                    <Header
                        actions={
                            <div className='mr-10'>
                                <SpaceBetween direction='horizontal' size='m'>
                                    <Button iconName='add-plus' variant='inline-link'>
                                        <Link to={`/chatbot/${uuidv4()}`}>New</Link>
                                    </Button>
                                    <Button
                                        iconAlt='Refresh list'
                                        iconName='refresh'
                                        variant='inline-link'
                                        onClick={() => doListSessions()}
                                    >
                                        Refresh
                                    </Button>
                                    {config[0].configuration.enabledComponents.deleteSessionHistory &&
                                    <Button
                                        iconAlt='Delete all sessions'
                                        iconName='delete-marker'
                                        variant='inline-link'
                                        onClick={() => doDeleteUserSessions()}
                                    >
                                        Delete all
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
