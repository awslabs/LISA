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
import SpaceBetween from '@cloudscape-design/components/space-between';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { Box, Button, ButtonDropdown, FormField, Grid, Input, Modal } from '@cloudscape-design/components';
import Link from '@cloudscape-design/components/link';

import { LisaProject } from '@/shared/model/project.model';
import { LisaChatSession } from '@/components/types';
import { getSessionDisplay } from '@/components/utils';
import { useNotificationService } from '@/shared/util/hooks';
import { useAppDispatch } from '@/config/store';
import { formatDate } from '@/shared/util/formats';
import styles from './Sessions.module.css';
import {
    useCreateProjectMutation,
    useRenameProjectMutation,
    useDeleteProjectMutation,
} from '@/shared/reducers/project.reducer';
import { useAssignSessionProjectMutation } from '@/shared/reducers/session.reducer';

type ProjectsSectionProps = {
    projects: LisaProject[];
    sessions: LisaChatSession[];
    maxProjects: number;
    currentSessionId?: string;
    onNavigate: (sessionId: string) => void;
};

export function ProjectsSection ({ projects, sessions, maxProjects, currentSessionId, onNavigate }: ProjectsSectionProps) {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);

    const [createProject] = useCreateProjectMutation();
    const [renameProject] = useRenameProjectMutation();
    const [deleteProject] = useDeleteProjectMutation();
    const [assignSessionProject] = useAssignSessionProjectMutation();

    // Create project modal
    const [createModalVisible, setCreateModalVisible] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const atLimit = projects.length >= maxProjects;


    useEffect(() => {
        const handler = () => !atLimit && setCreateModalVisible(true);
        window.addEventListener('lisa:create-project', handler);
        return () => window.removeEventListener('lisa:create-project', handler);
    }, [atLimit]);

    // Rename project modal
    const [renameModalVisible, setRenameModalVisible] = useState(false);
    const [projectToRename, setProjectToRename] = useState<LisaProject | null>(null);
    const [renameValue, setRenameValue] = useState('');
    const [isRenaming, setIsRenaming] = useState(false);

    // Delete project modal
    const [deleteModalVisible, setDeleteModalVisible] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<LisaProject | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const sessionsByProject = useCallback((projectId: string) =>
        sessions.filter((s) => s.projectId === projectId),
    [sessions]);

    const handleCreateConfirm = async () => {
        if (!newProjectName.trim()) return;
        setIsCreating(true);
        try {
            await createProject({ name: newProjectName.trim() }).unwrap();
            notificationService.generateNotification('Project created', 'success');
            setCreateModalVisible(false);
            setNewProjectName('');
        } catch {
            notificationService.generateNotification('Failed to create project', 'error');
        } finally {
            setIsCreating(false);
        }
    };

    const handleRenameConfirm = async () => {
        if (!projectToRename || !renameValue.trim()) return;
        setIsRenaming(true);
        try {
            await renameProject({ projectId: projectToRename.projectId, name: renameValue.trim() }).unwrap();
            notificationService.generateNotification('Project renamed', 'success');
            setRenameModalVisible(false);
            setProjectToRename(null);
        } catch {
            notificationService.generateNotification('Failed to rename project', 'error');
        } finally {
            setIsRenaming(false);
        }
    };

    const handleDeleteOnly = async () => {
        if (!projectToDelete) return;
        setIsDeleting(true);
        try {
            await deleteProject({ projectId: projectToDelete.projectId, deleteSessions: false }).unwrap();
            notificationService.generateNotification('Project deleted; sessions returned to History', 'success');
            setDeleteModalVisible(false);
            setProjectToDelete(null);
        } catch {
            notificationService.generateNotification('Failed to delete project', 'error');
        } finally {
            setIsDeleting(false);
        }
    };

    const handleDeleteWithSessions = async () => {
        if (!projectToDelete) return;
        setIsDeleting(true);
        try {
            await deleteProject({ projectId: projectToDelete.projectId, deleteSessions: true }).unwrap();
            notificationService.generateNotification('Project and sessions deleted', 'success');
            setDeleteModalVisible(false);
            setProjectToDelete(null);
        } catch {
            notificationService.generateNotification('Failed to delete project and sessions', 'error');
        } finally {
            setIsDeleting(false);
        }
    };

    const handleUnassign = async (session: LisaChatSession) => {
        if (!session.projectId) return;
        try {
            await assignSessionProject({ projectId: session.projectId, sessionId: session.sessionId, unassign: true }).unwrap();
        } catch {
            notificationService.generateNotification('Failed to remove session from project', 'error');
        }
    };

    return (
        <>
            <SpaceBetween size='s' direction='vertical'>
                <Box margin={{ top: 's' }}>
                    <Box fontSize='heading-s' fontWeight='bold' color='text-label'>Projects</Box>
                </Box>

                {projects.length === 0 ? (
                    <Box variant='small' color='text-status-inactive'>No projects yet</Box>
                ) : (
                    <SpaceBetween size='xs'>
                        {projects.map((project) => {
                            const projectSessions = sessionsByProject(project.projectId);
                            return (
                                <ExpandableSection
                                    key={project.projectId}
                                    headerText={project.name.length > 15 ? `${project.name.slice(0, 15)}...` : project.name}
                                    headerActions={
                                        <ButtonDropdown
                                            items={[
                                                { id: 'rename', text: 'Rename', iconName: 'edit' },
                                                { id: 'delete', text: 'Delete', iconName: 'delete-marker' },
                                            ]}
                                            ariaLabel={`Project actions for ${project.name}`}
                                            variant='icon'
                                            onItemClick={(e) => {
                                                if (e.detail.id === 'rename') {
                                                    setProjectToRename(project);
                                                    setRenameValue(project.name);
                                                    setRenameModalVisible(true);
                                                } else if (e.detail.id === 'delete') {
                                                    setProjectToDelete(project);
                                                    setDeleteModalVisible(true);
                                                }
                                            }}
                                        />
                                    }
                                    defaultExpanded
                                >
                                    {projectSessions.length === 0 ? (
                                        <Box variant='small' color='text-status-inactive'>No sessions</Box>
                                    ) : (
                                        <SpaceBetween size='xxs'>
                                            {projectSessions.map((session) => (
                                                <Box
                                                    key={session.sessionId}
                                                    padding='xxs'
                                                    className={session.sessionId === currentSessionId ? styles.sessionItemActive : styles.sessionItem}
                                                >
                                                    <Grid gridDefinition={[{ colspan: 10 }, { colspan: 2 }]}>
                                                        <Box>
                                                            <SpaceBetween size='xxs' direction='vertical'>
                                                                <Link onClick={() => onNavigate(session.sessionId)}>
                                                                    <Box
                                                                        color={session.sessionId === currentSessionId ? 'text-status-info' : 'text-status-inactive'}
                                                                        fontWeight={session.sessionId === currentSessionId ? 'bold' : 'heavy'}
                                                                    >
                                                                        {getSessionDisplay(session, 40)}
                                                                    </Box>
                                                                </Link>
                                                                <Box variant='small' color='text-status-inactive' fontSize='body-s' fontWeight='light'>
                                                                    {formatDate(session.lastUpdated || session.startTime)}
                                                                </Box>
                                                            </SpaceBetween>
                                                        </Box>
                                                        <Box>
                                                            <ButtonDropdown
                                                                items={[{ id: 'remove-from-project', text: 'Remove from Project', iconName: 'undo' }]}
                                                                ariaLabel='Session actions'
                                                                variant='icon'
                                                                onItemClick={() => handleUnassign(session)}
                                                            />
                                                        </Box>
                                                    </Grid>
                                                </Box>
                                            ))}
                                        </SpaceBetween>
                                    )}
                                </ExpandableSection>
                            );
                        })}
                    </SpaceBetween>
                )}
            </SpaceBetween>

            {/* Create Project Modal */}
            <Modal
                onDismiss={() => {
                    setCreateModalVisible(false); setNewProjectName('');
                }}
                visible={createModalVisible}
                header='New Project'
                footer={
                    <Box float='right'>
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button data-testid='create-project-cancel' variant='link' onClick={() => {
                                setCreateModalVisible(false); setNewProjectName('');
                            }}>
                                Cancel
                            </Button>
                            <Button
                                variant='primary'
                                onClick={handleCreateConfirm}
                                disabled={!newProjectName.trim() || isCreating || atLimit}
                                loading={isCreating}
                            >
                                Create
                            </Button>
                        </SpaceBetween>
                    </Box>
                }
            >
                <FormField label='Project Name'>
                    <Input
                        data-testid='input-placeholder'
                        value={newProjectName}
                        onChange={({ detail }) => setNewProjectName(detail.value)}
                        placeholder='Enter project name...'
                        onKeyDown={(e) => {
                            if (e.detail.key === 'Enter' && newProjectName.trim()) handleCreateConfirm();
                        }}
                    />
                </FormField>
            </Modal>

            {/* Rename Project Modal */}
            <Modal
                onDismiss={() => {
                    setRenameModalVisible(false); setProjectToRename(null);
                }}
                visible={renameModalVisible}
                header='Rename Project'
                footer={
                    <Box float='right'>
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button data-testid='rename-project-cancel' variant='link' onClick={() => {
                                setRenameModalVisible(false); setProjectToRename(null);
                            }}>
                                Cancel
                            </Button>
                            <Button
                                variant='primary'
                                onClick={handleRenameConfirm}
                                disabled={!renameValue.trim() || isRenaming}
                                loading={isRenaming}
                            >
                                Rename
                            </Button>
                        </SpaceBetween>
                    </Box>
                }
            >
                <FormField label='Project Name'>
                    <Input
                        data-testid='rename-project-input'
                        value={renameValue}
                        onChange={({ detail }) => setRenameValue(detail.value)}
                        onKeyDown={(e) => {
                            if (e.detail.key === 'Enter' && renameValue.trim()) handleRenameConfirm();
                        }}
                    />
                </FormField>
            </Modal>

            {/* Delete Project Modal — two explicit action buttons */}
            <Modal
                onDismiss={() => {
                    setDeleteModalVisible(false); setProjectToDelete(null);
                }}
                visible={deleteModalVisible}
                header='Delete Project'
                footer={
                    <Box float='right'>
                        <SpaceBetween direction='horizontal' size='xs'>
                            <Button data-testid='delete-project-cancel' variant='link' onClick={() => {
                                setDeleteModalVisible(false); setProjectToDelete(null);
                            }}>
                                Cancel
                            </Button>
                            <Button
                                variant='normal'
                                onClick={handleDeleteOnly}
                                disabled={isDeleting}
                                loading={isDeleting}
                            >
                                Delete project only
                            </Button>
                            <Button
                                variant='primary'
                                onClick={handleDeleteWithSessions}
                                disabled={isDeleting}
                                loading={isDeleting}
                            >
                                Delete project and sessions
                            </Button>
                        </SpaceBetween>
                    </Box>
                }
            >
                <Box>
                    Delete <strong>{projectToDelete?.name}</strong>? Choose whether to also delete its sessions or return them to History.
                </Box>
            </Modal>
        </>
    );
}

export default ProjectsSection;
