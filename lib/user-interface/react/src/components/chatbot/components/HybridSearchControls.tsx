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

import { Box, Button, FormField, Grid, Icon, Input, Popover, Slider, SpaceBetween } from '@cloudscape-design/components';

export type HybridSearchControlsProps = {
    vectorWeight: number;
    lexicalWeight: number;
    onChange: (weights: { vectorWeight: number; lexicalWeight: number }) => void;
    disabled?: boolean;
    disabledReason?: string;
};

const PRESETS = [
    { label: 'Balanced', vectorWeight: 0.5, lexicalWeight: 0.5 },
    { label: 'Semantic-heavy', vectorWeight: 0.8, lexicalWeight: 0.2 },
    { label: 'Lexical-heavy', vectorWeight: 0.3, lexicalWeight: 0.7 },
] as const;

function roundTo1 (value: number): number {
    return Math.round(value * 10) / 10;
}

export default function HybridSearchControls ({ vectorWeight, lexicalWeight, onChange, disabled, disabledReason }: HybridSearchControlsProps) {
    const handleVectorSliderChange = ({ detail }: { detail: { value: number } }) => {
        const clamped = Math.min(1, Math.max(0, roundTo1(detail.value)));
        onChange({ vectorWeight: clamped, lexicalWeight: roundTo1(1 - clamped) });
    };

    const handleLexicalSliderChange = ({ detail }: { detail: { value: number } }) => {
        const clamped = Math.min(1, Math.max(0, roundTo1(detail.value)));
        onChange({ vectorWeight: roundTo1(1 - clamped), lexicalWeight: clamped });
    };

    const handleVectorInputChange = ({ detail }: { detail: { value: string } }) => {
        const parsed = parseFloat(detail.value);
        if (!isNaN(parsed) && parsed >= 0 && parsed <= 1) {
            const clamped = roundTo1(parsed);
            onChange({ vectorWeight: clamped, lexicalWeight: roundTo1(1 - clamped) });
        }
    };

    const handleLexicalInputChange = ({ detail }: { detail: { value: string } }) => {
        const parsed = parseFloat(detail.value);
        if (!isNaN(parsed) && parsed >= 0 && parsed <= 1) {
            const clamped = roundTo1(parsed);
            onChange({ vectorWeight: roundTo1(1 - clamped), lexicalWeight: clamped });
        }
    };

    const disabledInfo = disabled && disabledReason ? (
        <Popover
            dismissButton={false}
            position='top'
            size='small'
            triggerType='custom'
            content={<Box color='text-body-secondary'>{disabledReason}</Box>}
        >
            <Box display='inline-block' margin={{ left: 'xs' }}>
                <Icon name='status-info' variant='link' />
            </Box>
        </Popover>
    ) : null;

    return (
        <SpaceBetween size='s'>
            <FormField label={<span>Vector weight{disabledInfo}</span>} constraintText='0.0 to 1.0 in 0.1 increments — weights must sum to 1'>
                <Grid gridDefinition={[{ colspan: 9 }, { colspan: 3 }]}>
                    <Slider
                        ariaLabel='Vector weight'
                        value={vectorWeight}
                        min={0}
                        max={1}
                        step={0.1}
                        tickMarks={true}
                        onChange={handleVectorSliderChange}
                        disabled={disabled}
                    />
                    <Input
                        ariaLabel='Vector weight'
                        type='number'
                        step={0.1}
                        inputMode='decimal'
                        value={vectorWeight.toString()}
                        onChange={handleVectorInputChange}
                        disabled={disabled}
                        disableBrowserAutocorrect={true}
                    />
                </Grid>
            </FormField>
            <FormField label={<span>Lexical weight{disabledInfo}</span>} constraintText='Automatically adjusted to complement vector weight'>
                <Grid gridDefinition={[{ colspan: 9 }, { colspan: 3 }]}>
                    <Slider
                        ariaLabel='Lexical weight'
                        value={lexicalWeight}
                        min={0}
                        max={1}
                        step={0.1}
                        tickMarks={true}
                        onChange={handleLexicalSliderChange}
                        disabled={disabled}
                    />
                    <Input
                        ariaLabel='Lexical weight'
                        type='number'
                        step={0.1}
                        inputMode='decimal'
                        value={lexicalWeight.toString()}
                        onChange={handleLexicalInputChange}
                        disabled={disabled}
                        disableBrowserAutocorrect={true}
                    />
                </Grid>
            </FormField>
            <SpaceBetween size='xs' direction='horizontal'>
                {PRESETS.map((preset) => (
                    <Button
                        key={preset.label}
                        variant='normal'
                        disabled={disabled}
                        onClick={() => onChange({ vectorWeight: preset.vectorWeight, lexicalWeight: preset.lexicalWeight })}
                    >
                        {preset.label}
                    </Button>
                ))}
            </SpaceBetween>
        </SpaceBetween>
    );
}
