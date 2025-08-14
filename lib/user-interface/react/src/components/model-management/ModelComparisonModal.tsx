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

import { ReactElement } from 'react';
import {
    Modal,
    Box,
    SpaceBetween,
    Header,
    Button,
    Alert
} from '@cloudscape-design/components';
import { IModel } from '../../shared/model/model-management.model';
import { useModelComparison } from './hooks/useModelComparison.hook';
import {
    ModelSelectionSection,
    PromptInputSection,
    ComparisonResults
} from './components/ModelComparisonComponents';
import { MESSAGES } from './config/modelComparison.config';

export type ModelComparisonModalProps = {
    visible: boolean;
    setVisible: (visible: boolean) => void;
    models: IModel[];
};

export function ModelComparisonModal ({ visible, setVisible, models }: ModelComparisonModalProps): ReactElement {
    const {
        // State
        modelSelections,
        prompt,
        responses,
        availableModels,
        canCompare,

        // Actions
        setPrompt,
        addModelComparison,
        removeModelComparison,
        updateModelSelection,
        getAvailableModelsForSelection,
        handleCompare,
        resetComparison
    } = useModelComparison(models);

    const handleClose = () => {
        setVisible(false);
        resetComparison();
    };

    return (
        <Modal
            onDismiss={handleClose}
            visible={visible}
            size='max'
            header={
                <Header variant='h1'>
                    Model Comparison
                </Header>
            }
            footer={
                <Box float='right'>
                    <Button variant='link' onClick={handleClose}>
                        Close
                    </Button>
                </Box>
            }
        >
            <SpaceBetween size='l'>
                <ModelSelectionSection
                    modelSelections={modelSelections}
                    availableModels={availableModels}
                    onAddModel={addModelComparison}
                    onRemoveModel={removeModelComparison}
                    onUpdateSelection={updateModelSelection}
                    getAvailableModelsForSelection={getAvailableModelsForSelection}
                />

                <PromptInputSection
                    prompt={prompt}
                    onPromptChange={setPrompt}
                    onCompare={handleCompare}
                    canCompare={canCompare}
                />

                {responses.length > 0 && (
                    <ComparisonResults
                        prompt={prompt}
                        responses={responses}
                        models={models}
                    />
                )}

                {availableModels.length < 2 && (
                    <Alert type='warning' header='Insufficient Models'>
                        {MESSAGES.INSUFFICIENT_MODELS}
                    </Alert>
                )}
            </SpaceBetween>
        </Modal>
    );
}

export default ModelComparisonModal;
