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
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { ButtonDropdown, Input, Popover, Modal, FormField, Grid } from '@cloudscape-design/components';
import Button from '@cloudscape-design/components/button';

import { useLazyGetConfigurationQuery } from '@/shared/reducers/configuration.reducer';
import {
    sessionApi,
    useDeleteAllSessionsForUserMutation,
    useDeleteSessionByIdMutation,
    useLazyGetSessionByIdQuery,
    useListSessionsQuery,
    useUpdateSessionNameMutation,
} from '@/shared/reducers/session.reducer';
import { useAppDispatch } from '@/config/store';
import { useNotificationService } from '@/shared/util/hooks';
import { useEffect, useState, useMemo } from 'react';
import { useAuth } from 'react-oidc-context';
import { IConfiguration } from '@/shared/model/configuration.model';
import { useNavigate } from 'react-router-dom';
import { getSessionDisplay, messageContainsImage, messageContainsVideo } from '@/components/utils';
import { LisaChatSession } from '@/components/types';
import Box from '@cloudscape-design/components/box';
import JSZip from 'jszip';
import { downloadFile } from '@/shared/util/downloader';
import { setConfirmationModal } from '@/shared/reducers/modal.reducer';
import styles from './Sessions.module.css';



export function Sessions({ newSession }) {
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
    const [updateSessionName, {
        isSuccess: isUpdateSessionNameSuccess,
        isError: isUpdateSessionNameError,
        error: updateSessionNameError,
        isLoading: isUpdateSessionNameLoading,
    }] = useUpdateSessionNameMutation();
    const [getConfiguration] = useLazyGetConfigurationQuery();
    const [config, setConfig] = useState<IConfiguration>();
    const [searchQuery, setSearchQuery] = useState<string>('');

    const [renameModalVisible, setRenameModalVisible] = useState<boolean>(false);
    const [sessionToRename, setSessionToRename] = useState<LisaChatSession | null>(null);
    const [newSessionName, setNewSessionName] = useState<string>('');
    const [sessionBeingDeleted, setSessionBeingDeleted] = useState<string | null>(null);
    const { data: sessions, isLoading: isSessionsLoading } = useListSessionsQuery(null, { refetchOnMountOrArgChange: 5 });

    // Filter sessions based on search query
    const filteredSessions = useMemo(() => {
        if (!searchQuery.trim()) {
            return sessions || [];
        }
        return (sessions || [])
            .filter((session) => getSessionDisplay(session).toLowerCase().includes(searchQuery.toLowerCase()));
    }, [sessions, searchQuery]);

    // Group and sort sessions by time periods
    const groupedSessions = useMemo(() => {
        const now = new Date();
        const groups = {
            'Last Day': [] as LisaChatSession[],
            'Last 7 Days': [] as LisaChatSession[],
            'Last Month': [] as LisaChatSession[],
            'Last 3 Months': [] as LisaChatSession[],
            'Older': [] as LisaChatSession[]
        };

        filteredSessions.forEach((session) => {
            // Use lastUpdated if available, otherwise fallback to startTime for backward compatibility
            const lastUpdated = session.lastUpdated || session.startTime;
            const sessionDate = new Date(lastUpdated);
            const diffInDays = (now.getTime() - sessionDate.getTime()) / (1000 * 60 * 60 * 24);

            if (diffInDays <= 1) {
                groups['Last Day'].push(session);
            } else if (diffInDays <= 7) {
                groups['Last 7 Days'].push(session);
            } else if (diffInDays <= 30) {
                groups['Last Month'].push(session);
            } else if (diffInDays <= 90) {
                groups['Last 3 Months'].push(session);
            } else {
                groups['Older'].push(session);
            }
        });

        // Sort sessions within each group by lastUpdated (most recent first)
        Object.keys(groups).forEach((key) => {
            groups[key as keyof typeof groups].sort((a, b) => {
                const aTime = new Date(a.lastUpdated || a.startTime).getTime();
                const bTime = new Date(b.lastUpdated || b.startTime).getTime();
                return bTime - aTime; // Descending order (newest first)
            });
        });

        return groups;
    }, [filteredSessions]);

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
            // Only reload if we are deleting the current session or there is no current session (/ai-assistant with no session ID)
            if (sessionBeingDeleted === currentSessionId || !currentSessionId) {
                newSession();
            }

            // Reset the tracking state
            setSessionBeingDeleted(null);
        } else if (!isDeleteByIdLoading && isDeleteByIdError) {
            const errorMessage = 'message' in deleteByIdError ? deleteByIdError.message : 'Unknown error';
            notificationService.generateNotification(`Error deleting session: ${errorMessage}`, 'error');

            // Reset the tracking state on error too
            setSessionBeingDeleted(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteByIdSuccess, isDeleteByIdError, deleteByIdError, isDeleteByIdLoading]);

    useEffect(() => {
        if (!isDeleteUserSessionsLoading && isDeleteUserSessionsSuccess) {
            notificationService.generateNotification('Successfully deleted all user sessions', 'success');
        } else if (!isDeleteUserSessionsLoading && isDeleteUserSessionsError) {
            const errorMessage = 'message' in deleteUserSessionsError ? deleteUserSessionsError.message : 'Unknown error';
            notificationService.generateNotification(`Error deleting user sessions: ${errorMessage}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDeleteUserSessionsSuccess, isDeleteUserSessionsError, deleteUserSessionsError, isDeleteUserSessionsLoading]);

    useEffect(() => {
        if (!isUpdateSessionNameLoading && isUpdateSessionNameSuccess) {
            notificationService.generateNotification('Successfully renamed session', 'success');
            setRenameModalVisible(false);
            setSessionToRename(null);
            setNewSessionName('');
        } else if (!isUpdateSessionNameLoading && isUpdateSessionNameError) {
            const errorMessage = 'message' in updateSessionNameError ? updateSessionNameError.message : 'Unknown error';
            notificationService.generateNotification(`Error renaming session: ${errorMessage}`, 'error');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isUpdateSessionNameSuccess, isUpdateSessionNameError, updateSessionNameError, isUpdateSessionNameLoading]);

    const handleRenameSession = (session: LisaChatSession) => {
        setSessionToRename(session);
        setNewSessionName(getSessionDisplay(session));
        setRenameModalVisible(true);
    };

    const handleRenameConfirm = () => {
        if (sessionToRename && newSessionName.trim()) {
            const updatedSession = {
                ...sessionToRename,
                name: newSessionName.trim()
            };
            updateSessionName(updatedSession);
        }
    };

    const handleRenameCancel = () => {
        setRenameModalVisible(false);
        setSessionToRename(null);
        setNewSessionName('');
    };

    return (
        <div className='p-5'>
            <SpaceBetween size='l' direction='vertical'>
                <Header>
                    History
                </Header>
                    <Input
                        value={searchQuery}
                        onChange={({ detail }) => setSearchQuery(detail.value)}
                        placeholder='Search sessions by name'
                        clearAriaLabel='Clear search'
                        type='search'
                        style={
                            {
                                root: {
                                    borderColor: {
                                        focus: filteredSessions.length >= 1 ? '' : '#ff7a7a',
                                    }
                                }
                            }
                        }
                    />
                    {searchQuery && (
                        <Box variant='small' color={filteredSessions.length >= 1 ? 'text-status-info' :'text-status-error'}>
                            Found {filteredSessions.length} session{filteredSessions.length !== 1 ? 's' : ''}
                        </Box>
                    )}
                <SpaceBetween direction='horizontal' size='xs'>
                    <Button
                        iconName='add-plus'
                        variant='inline-icon'
                        onClick={newSession}
                        ariaLabel='New Session'
                    />
                    <Button
                        iconAlt='Refresh list'
                        iconName='refresh'
                        variant='inline-icon'
                        onClick={() => dispatch(sessionApi.util.invalidateTags(['sessions']))}
                        ariaLabel='Refresh Sessions'
                    />
                    {config?.configuration.enabledComponents.deleteSessionHistory &&
                        <Button
                            iconAlt='Delete sessions'
                            iconName='remove'
                            variant='inline-icon'
                            onClick={() =>
                                dispatch(
                                    setConfirmationModal({
                                        action: 'Delete',
                                        resourceName: 'All Sessions',
                                        onConfirm: () => deleteUserSessions(),
                                        description: 'This will delete all of your user sessions.'
                                    })
                                )}
                            ariaLabel='Delete All Sessions'
                        />}
                </SpaceBetween>
            </SpaceBetween>

            {isSessionsLoading && (
                <Box textAlign='center' padding='l'>
                    <SpaceBetween size='s' direction='vertical'>
                        <Box color='text-status-info'>Loading sessions...</Box>
                        <Box variant='small' color='text-status-inactive'>Please wait while we fetch your session history</Box>
                    </SpaceBetween>
                </Box>
            )}

            {!isSessionsLoading && (
                <div className='pt-2'>
                    {filteredSessions.length === 0 ? (
                        <Box textAlign='center' padding='l'>
                            <SpaceBetween size='s' direction='vertical'>
                                <Box color='text-status-inactive'>No sessions</Box>
                                {searchQuery && (
                                    <Box variant='small' color='text-status-inactive'>
                                        Try adjusting your search query
                                    </Box>
                                )}
                                {!searchQuery && (
                                    <Box variant='small' color='text-status-inactive'>
                                        Start a new conversation to create your first session
                                    </Box>
                                )}
                            </SpaceBetween>
                        </Box>
                    ) : (
                        <SpaceBetween size='s'>
                            {(() => {
                                const timeGroups = Object.entries(groupedSessions);

                                return timeGroups.map(([timeGroup, sessions]) => {
                                    if (sessions.length === 0) return null;

                                    return (
                                        <ExpandableSection
                                            key={timeGroup}
                                            headerText={timeGroup}
                                            defaultExpanded={timeGroup === 'Last Day' || timeGroup === 'Last 7 Days'}
                                        >
                                            <SpaceBetween size='xxs'>
                                                {sessions.map((item) => (
                                                    <Box 
                                                        key={item.sessionId} 
                                                        padding='xxs'
                                                        className={item.sessionId === currentSessionId ? styles.sessionItemActive : styles.sessionItem}
                                                    >
                                                        <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]}>
                                                            <Box>
                                                                <Link onClick={() => navigate(`/ai-assistant/${item.sessionId}`)}>
                                                                    <Box
                                                                        color={item.sessionId === currentSessionId ? 'text-status-info' : 'text-status-inactive'}
                                                                        fontWeight={item.sessionId === currentSessionId ? 'bold' : 'normal'}
                                                                    >
                                                                        {getSessionDisplay(item, 40)}
                                                                    </Box>
                                                                </Link>
                                                            </Box>
                                                            <Box>
                                                                <ButtonDropdown
                                                                    items={[
                                                                        { id: 'rename-session', text: 'Rename Session', iconName: 'edit' },
                                                                        { id: 'download-session', text: 'Download Session', iconName: 'download' },
                                                                        { id: 'export-media', text: 'Export AI Media', iconName: 'folder' },
                                                                        ...(config?.configuration.enabledComponents.deleteSessionHistory ? [{ id: 'delete-session', text: 'Delete Session', iconName: 'delete-marker' as const }] : [])
                                                                    ]}
                                                                    ariaLabel='Control instance'
                                                                    variant='icon'
                                                                    onItemClick={(e) => {
                                                                        if (e.detail.id === 'delete-session') {
                                                                            dispatch(
                                                                                setConfirmationModal({
                                                                                    action: 'Delete',
                                                                                    resourceName: 'Session',
                                                                                    onConfirm: () => {
                                                                                        setSessionBeingDeleted(item.sessionId);
                                                                                        deleteById(item.sessionId);
                                                                                    },
                                                                                    description: `This will delete the Session: ${item.sessionId}.`
                                                                                })
                                                                            );
                                                                        } else if (e.detail.id === 'download-session') {
                                                                            getSessionById(item.sessionId).then((resp) => {
                                                                                const sess: LisaChatSession = resp.data;
                                                                                const file = new Blob([JSON.stringify(sess, null, 2)], { type: 'application/json' });
                                                                                downloadFile(URL.createObjectURL(file), `${sess.sessionId}.json`);
                                                                            });
                                                                        } else if (e.detail.id === 'export-media') {
                                                                            getSessionById(item.sessionId).then(async (resp) => {
                                                                                const sess: LisaChatSession = resp.data;
                                                                                // Extract media with type information to distinguish images from videos
                                                                                const media = sess.history.filter((msg) => msg.type === 'ai' && (messageContainsImage(msg.content) || messageContainsVideo(msg.content)))
                                                                                    .flatMap((msg) => {
                                                                                        if (Array.isArray(msg.content)) {
                                                                                            return msg.content
                                                                                                .filter((contentItem: any) => (contentItem.type === 'image_url' && contentItem.image_url?.url) || (contentItem.type === 'video_url' && contentItem.video_url?.url))
                                                                                                .map((contentItem: any) => ({
                                                                                                    url: contentItem.type === 'image_url' ? contentItem.image_url.url as string : contentItem.video_url.url as string,
                                                                                                    mediaType: contentItem.type === 'image_url' ? 'image' : 'video' as 'image' | 'video'
                                                                                                }));
                                                                                        }
                                                                                        return [];
                                                                                    });

                                                                                if (media.length === 0) {
                                                                                    notificationService.generateNotification('No media found to export', 'info');
                                                                                } else {
                                                                                    const zip = new JSZip();
                                                                                    let imageCount = 0;
                                                                                    let videoCount = 0;
                                                                                    const mediaPromises = media.map(async (mediaItem) => {
                                                                                        try {
                                                                                            const response = await fetch(mediaItem.url);
                                                                                            const blob = await response.blob();
                                                                                            if (mediaItem.mediaType === 'image') {
                                                                                                imageCount++;
                                                                                                zip.file(`image_${imageCount}.png`, blob, { binary: true });
                                                                                            } else {
                                                                                                videoCount++;
                                                                                                zip.file(`video_${videoCount}.mp4`, blob, { binary: true });
                                                                                            }
                                                                                        } catch (error) {
                                                                                            console.error(`Error processing ${mediaItem.mediaType}:`, error);
                                                                                        }
                                                                                    });

                                                                                    // Wait for all media to be processed
                                                                                    await Promise.all(mediaPromises);
                                                                                    const content = await zip.generateAsync({ type: 'blob' });
                                                                                    downloadFile(URL.createObjectURL(content), `${sess.sessionId}-media.zip`);
                                                                                }
                                                                            });
                                                                        } else if (e.detail.id === 'rename-session') {
                                                                            handleRenameSession(item);
                                                                        }
                                                                    }}
                                                                />
                                                            </Box>
                                                        </Grid>
                                                    </Box>
                                                ))}
                                            </SpaceBetween>
                                        </ExpandableSection>
                                    );
                                });
                            })()}
                        </SpaceBetween>
                    )}
                </div>
            )}

            {/* Rename Session Modal */}
            <Modal
                onDismiss={handleRenameCancel}
                visible={renameModalVisible}
                header='Rename Session'
                footer={
                    <Box float='right'>
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button variant='link' onClick={handleRenameCancel}>
                                Cancel
                            </Button>
                            <Button
                                variant='primary'
                                onClick={handleRenameConfirm}
                                disabled={!newSessionName.trim() || isUpdateSessionNameLoading}
                                loading={isUpdateSessionNameLoading}
                            >
                                Rename
                            </Button>
                        </SpaceBetween>
                    </Box>
                }
            >
                <SpaceBetween size='m'>
                    <FormField
                        label='Session Name'
                        description='Enter a new name for this session'
                        controlId='session-rename-input'
                    >
                        <Input
                            value={newSessionName}
                            onChange={({ detail }) => setNewSessionName(detail.value)}
                            placeholder='Enter session name...'
                            onKeyDown={(e) => {
                                if (e.detail.key === 'Enter' && newSessionName.trim() && !isUpdateSessionNameLoading) {
                                    handleRenameConfirm();
                                }
                            }}
                        />
                    </FormField>
                </SpaceBetween>
            </Modal>
        </div>
    );
}
export default Sessions;
