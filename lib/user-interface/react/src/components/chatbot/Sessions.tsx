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

import SpaceBetween from '@cloudscape-design/components/space-between';
import Link from '@cloudscape-design/components/link';
import Header from '@cloudscape-design/components/header';
import { ButtonDropdown, Grid} from '@cloudscape-design/components';
import Button from '@cloudscape-design/components/button';
import { useCollection } from '@cloudscape-design/collection-hooks';
import { useLazyGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';
import {
    sessionApi,
    useDeleteAllSessionsForUserMutation,
    useDeleteSessionByIdMutation, useLazyGetSessionByIdQuery,
    useListSessionsQuery,
} from '../../shared/reducers/session.reducer';
import { useAppDispatch } from '../../config/store';
import { useNotificationService } from '../../shared/util/hooks';
import { useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { IConfiguration } from '../../shared/model/configuration.model';
import { useNavigate } from 'react-router-dom';
import { truncateText } from '../../shared/util/formats';
import { fetchImage, getDisplayableMessage, messageContainsImage } from '@/components/utils';
import { LisaChatSession } from '@/components/types';
import Box from '@cloudscape-design/components/box';
import React from 'react';
import JSZip from 'jszip';
import { downloadFile } from '@/shared/util/downloader';

export function Sessions ({newSession}) {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const auth = useAuth();
    const navigate = useNavigate();
    const [getSessionById] = useLazyGetSessionByIdQuery();
    const currentSessionId = window.location.href.includes('ai-assistant/') ? window.location.href.split('ai-assistant/')[1] : undefined;


    const [deleteById, {
        isSuccess: isDeleteByIdSuccess,
        isError: isDeleteByIdError,
        error: deleteByIdError,
        isLoading: isDeleteByIdLoading,
    }] = useDeleteSessionByIdMutation();
    const [deleteUserSessions, {
        isSuccess: isDeleteUserSessionsSuccess,
        isError: isDeleteUserSessionsError,
        error: deleteUserSessionsError,
        isLoading: isDeleteUserSessionsLoading,
    }] = useDeleteAllSessionsForUserMutation();
    const [getConfiguration] = useLazyGetConfigurationQuery();
    const [config, setConfig] = useState<IConfiguration>();
    const { data: sessions } = useListSessionsQuery(null, { refetchOnMountOrArgChange: 5 });
    const { items } = useCollection(sessions || [], {
        sorting: {
            defaultState: {
                sortingColumn: {
                    sortingField: 'StartTime',
                },
                isDescending: true,
            },
        },
    });

    useEffect(() => {
        if (!auth.isLoading && auth.isAuthenticated) {
            getConfiguration('global').then((resp) => {
                if (resp.data && resp.data.length > 0) {
                    setConfig(resp.data[0]);
                }
            });
        }
    }, [auth, getConfiguration]);

    useEffect(() => {
        if (!isDeleteByIdLoading && isDeleteByIdSuccess) {
            notificationService.generateNotification('Successfully deleted session', 'success');
            navigate('ai-assistant');
            newSession();
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
        <div className='p-9'>
            <SpaceBetween size={'xl'} direction={'vertical'}>
                <Header
                    actions={
                        <div className='mr-10'>
                            <SpaceBetween direction='horizontal' size='m'>
                                <Button iconName='add-plus' variant='inline-link' onClick={() => {
                                    navigate('ai-assistant');
                                    newSession();
                                }}>
                                    New
                                </Button>
                                <Button
                                    iconAlt='Refresh list'
                                    iconName='refresh'
                                    variant='inline-link'
                                    onClick={() => dispatch(sessionApi.util.invalidateTags(['sessions']))}
                                >
                                    Refresh
                                </Button>
                                {config?.configuration.enabledComponents.deleteSessionHistory &&
                                <Button
                                    iconAlt='Delete sessions'
                                    iconName='delete-marker'
                                    variant='inline-link'
                                    onClick={() => deleteUserSessions()}
                                >
                                    Delete all
                                </Button>}
                            </SpaceBetween>
                        </div>
                    }
                >
                    History
                </Header>
            </SpaceBetween>
            <div className={'pt-5'}>
                <Grid gridDefinition={items.flatMap(() => [{ colspan: 10 }, { colspan: 2 }])}>
                    {items.map((item) => (
                        <React.Fragment key={item.sessionId}>
                            <SpaceBetween size={'s'} direction={'horizontal'} alignItems={'center'}>
                                <Link onClick={() => navigate(`ai-assistant/${item.sessionId}`)}>
                                    <Box color={item.sessionId === currentSessionId ? 'text-status-info' : 'text-status-inactive'}
                                        fontWeight={item.sessionId === currentSessionId ? 'bold' : 'normal'}>
                                        {truncateText(getDisplayableMessage(item.firstHumanMessage ?? ''), 40, '...')}
                                    </Box>
                                </Link>
                            </SpaceBetween>
                            <SpaceBetween size={'s'} alignItems={'end'}>
                                <ButtonDropdown
                                    items={[

                                        { id: 'delete-session', text: 'Delete Session', iconName: 'delete-marker'},
                                        { id: 'download-session', text: 'Download Session', iconName: 'download'},
                                        { id: 'export-images', text: 'Export AI Images', iconName: 'folder'},
                                    ]}
                                    ariaLabel='Control instance'
                                    variant='icon'
                                    onItemClick={(e) => {
                                        if (e.detail.id === 'delete-session'){
                                            deleteById(item.sessionId);
                                        } else if (e.detail.id === 'download-session'){
                                            getSessionById(item.sessionId).then((resp) => {
                                                const sess: LisaChatSession = resp.data;
                                                const file = new Blob([JSON.stringify(sess, null, 2)], { type: 'application/json' });
                                                downloadFile(URL.createObjectURL(file), `${sess.sessionId}.json`);
                                            });
                                        } else if (e.detail.id === 'export-images') {
                                            getSessionById(item.sessionId).then(async (resp) => {
                                                const sess: LisaChatSession = resp.data;
                                                const images = sess.history.filter((msg) => msg.type === 'ai' && messageContainsImage(msg.content))
                                                    .flatMap((msg) => {
                                                        return msg.content.map((contentItem) => {
                                                            if (contentItem.type === 'image_url') {
                                                                return contentItem.image_url.url;
                                                            }
                                                        });
                                                    });

                                                if (images.length === 0) {
                                                    notificationService.generateNotification('No images found to export', 'info');
                                                } else {
                                                    const zip = new JSZip();
                                                    const imagePromises = images.map(async (imageUrl, index) => {
                                                        try {
                                                            const blob = await fetchImage(imageUrl);
                                                            zip.file(`image_${index + 1}.png`, blob, {binary: true});
                                                        } catch (error) {
                                                            console.error(`Error processing image ${index + 1}:`, error);
                                                        }
                                                    });

                                                    // Wait for all images to be processed
                                                    await Promise.all(imagePromises);
                                                    const content = await zip.generateAsync({type: 'blob'});
                                                    downloadFile(URL.createObjectURL(content), `${sess.sessionId}-images.zip`);
                                                }
                                            });
                                        }
                                    }}
                                />
                            </SpaceBetween>
                        </React.Fragment>
                    ))}
                </Grid>
            </div>
        </div>
    );
}
export default Sessions;
