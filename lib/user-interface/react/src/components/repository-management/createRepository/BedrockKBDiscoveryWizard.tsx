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
import { Box, SpaceBetween, Wizard } from '@cloudscape-design/components';
import { KnowledgeBaseSelector } from './KnowledgeBaseSelector';
import { DataSourceMultiSelect } from './DataSourceMultiSelect';
import { KnowledgeBase, DataSourceSelection } from '@/types/bedrock-kb';

type BedrockKBDiscoveryWizardProps = {
    visible: boolean;
    onDismiss: () => void;
    onComplete: (kbId: string, kbName: string, kbDescription: string, selections: DataSourceSelection[]) => void;
    repositoryId?: string;
};

export function BedrockKBDiscoveryWizard ({
    visible,
    onDismiss,
    onComplete,
    repositoryId,
}: BedrockKBDiscoveryWizardProps): ReactElement {
    const [activeStepIndex, setActiveStepIndex] = useState(0);
    const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null);
    const [selectedDataSources, setSelectedDataSources] = useState<DataSourceSelection[]>([]);

    const handleNavigate = (detail: { requestedStepIndex: number; reason: string }) => {
        setActiveStepIndex(detail.requestedStepIndex);
    };

    const handleCancel = () => {
        // Reset state
        setActiveStepIndex(0);
        setSelectedKB(null);
        setSelectedDataSources([]);
        onDismiss();
    };

    const handleSubmit = () => {
        if (selectedKB && selectedDataSources.length > 0) {
            onComplete(
                selectedKB.knowledgeBaseId,
                selectedKB.name,
                selectedKB.description || '',
                selectedDataSources
            );
            // Reset state
            setActiveStepIndex(0);
            setSelectedKB(null);
            setSelectedDataSources([]);
        }
    };

    if (!visible) {
        return <></>;
    }

    return (
        <Wizard
            i18nStrings={{
                stepNumberLabel: (stepNumber) => `Step ${stepNumber}`,
                collapsedStepsLabel: (stepNumber, stepsCount) => `Step ${stepNumber} of ${stepsCount}`,
                skipToButtonLabel: (step) => `Skip to ${step.title}`,
                navigationAriaLabel: 'Steps',
                cancelButton: 'Cancel',
                previousButton: 'Previous',
                nextButton: 'Next',
                submitButton: 'Create Repository',
                optional: 'optional',
            }}
            onNavigate={handleNavigate}
            onCancel={handleCancel}
            onSubmit={handleSubmit}
            activeStepIndex={activeStepIndex}
            allowSkipTo
            steps={[
                {
                    title: 'Select Knowledge Base',
                    description: 'Choose a Bedrock Knowledge Base to connect',
                    content: (
                        <KnowledgeBaseSelector
                            selectedKbId={selectedKB?.knowledgeBaseId || null}
                            onSelect={setSelectedKB}
                        />
                    ),
                    isOptional: false,
                },
                {
                    title: 'Select Data Sources',
                    description: 'Choose which data sources to track as collections',
                    content: selectedKB ? (
                        <DataSourceMultiSelect
                            kbId={selectedKB.knowledgeBaseId}
                            repositoryId={repositoryId}
                            selectedDataSources={selectedDataSources}
                            onSelectionChange={setSelectedDataSources}
                        />
                    ) : (
                        <Box textAlign='center' padding={{ vertical: 'l' }}>
                            Please select a Knowledge Base first
                        </Box>
                    ),
                    isOptional: false,
                },
                {
                    title: 'Review and Create',
                    description: 'Review your selections before creating the repository',
                    content: (
                        <SpaceBetween size='l'>
                            <Box>
                                <Box variant='h3' padding={{ bottom: 's' }}>
                                    Knowledge Base
                                </Box>
                                <Box>
                                    <strong>Name:</strong> {selectedKB?.name || 'None selected'}
                                </Box>
                                <Box>
                                    <strong>ID:</strong> {selectedKB?.knowledgeBaseId || 'None selected'}
                                </Box>
                                {selectedKB?.description && (
                                    <Box>
                                        <strong>Description:</strong> {selectedKB.description}
                                    </Box>
                                )}
                            </Box>

                            <Box>
                                <Box variant='h3' padding={{ bottom: 's' }}>
                                    Selected Data Sources ({selectedDataSources.length})
                                </Box>
                                {selectedDataSources.length > 0 ? (
                                    <SpaceBetween size='s'>
                                        {selectedDataSources.map((ds) => (
                                            <Box key={ds.dataSourceId} padding={{ left: 's' }}>
                                                <Box>
                                                    <strong>{ds.dataSourceName}</strong>
                                                </Box>
                                                <Box variant='small' color='text-body-secondary'>
                                                    ID: {ds.dataSourceId}
                                                </Box>
                                                <Box variant='small' color='text-body-secondary'>
                                                    S3: s3://{ds.s3Bucket}/{ds.s3Prefix || ''}
                                                </Box>
                                            </Box>
                                        ))}
                                    </SpaceBetween>
                                ) : (
                                    <Box color='text-status-warning'>No data sources selected</Box>
                                )}
                            </Box>
                        </SpaceBetween>
                    ),
                    isOptional: false,
                },
            ]}
        />
    );
}
