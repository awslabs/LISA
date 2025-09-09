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

import React, { useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';
import { ButtonGroup, StatusIndicator } from '@cloudscape-design/components';
import { downloadSvgAsPng } from '../../../shared/util/downloader';

type MermaidDiagramProps = {
    chart: string;
    id?: string;
    isStreaming?: boolean;
};

const MermaidDiagram: React.FC<MermaidDiagramProps> = React.memo(({ chart, id, isStreaming }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string>('');
    const [svg, setSvg] = useState<string>('');
    const [isLoading, setIsLoading] = useState(true);
    const mermaidInitialized = useRef(false);
    const lastRenderedChart = useRef<string>('');

    // Initialize Mermaid once
    useEffect(() => {
        if (!mermaidInitialized.current) {
            mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                securityLevel: 'loose',
                fontFamily: 'Arial, sans-serif',
                suppressErrorRendering: true,
                fontSize: 14,
                flowchart: {
                    useMaxWidth: true,
                    htmlLabels: true,
                },
                sequence: {
                    useMaxWidth: true,
                    wrap: true,
                },
                gantt: {
                    useMaxWidth: true,
                },
            });
            mermaidInitialized.current = true;
        }
    }, []);


    // Render the diagram once
    useEffect(() => {
        const renderDiagram = async () => {
            // Skip rendering if we've already rendered this exact chart
            if (lastRenderedChart.current === chart && svg) {
                return;
            }

            if (!chart.trim()) {
                setError('Empty chart content');
                setIsLoading(false);
                return;
            }

            // Don't render during streaming or if syntax appears incomplete
            if (isStreaming) {
                setIsLoading(true);
                return;
            }

            setIsLoading(true);
            setError('');

            try {
                const diagramId = id || `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                const { svg: renderedSvg } = await mermaid.render(diagramId, chart);
                setSvg(renderedSvg);
                lastRenderedChart.current = chart;
            } catch (err) {
                console.error('Mermaid rendering error:', err);
                setError(`Failed to render diagram: ${err instanceof Error ? err.message : 'Unknown error'}`);
            } finally {
                setIsLoading(false);
            }
        };

        renderDiagram();
    }, [chart, id, svg, isStreaming]);

    const copyToClipboard = useCallback(async (content: string) => {
        try {
            await navigator.clipboard.writeText(content);
        } catch (err) {
            console.error('Failed to copy to clipboard:', err);
        }
    }, []);


    const handleButtonClick = useCallback(({ detail }: { detail: { id: string } }) => {
        if (detail.id === 'copy-code') {
            copyToClipboard(chart);
        } else if (detail.id === 'download-png') {
            // Find the SVG element in the container
            const svgElement = containerRef.current?.querySelector('svg');
            if (svgElement) {
                downloadSvgAsPng(svgElement, 'mermaid-diagram.png');
            }
        }
    }, [chart, copyToClipboard]);

    // Error state - show original code
    if (error) {
        return (
            <div style={{
                padding: '12px',
                backgroundColor: '#2d1b1b',
                border: '1px solid #d13212',
                borderRadius: '4px',
                color: '#ff6b6b',
                fontFamily: 'monospace',
                fontSize: '12px'
            }}>
                <strong>Mermaid Error:</strong> {error}
                <details style={{ marginTop: '8px' }}>
                    <summary style={{ cursor: 'pointer', color: '#ff9999' }}>
                        Show diagram source
                    </summary>
                    <pre style={{
                        marginTop: '8px',
                        padding: '8px',
                        backgroundColor: '#1a1a1a',
                        borderRadius: '2px',
                        overflow: 'auto',
                        fontSize: '11px'
                    }}>
                        {chart}
                    </pre>
                </details>
            </div>
        );
    }

    // Loading state
    if (isLoading || !svg) {
        return (
            <div style={{
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #444',
                borderRadius: '4px',
                color: '#888',
                textAlign: 'center'
            }}>
                Rendering Mermaid diagram...
            </div>
        );
    }

    const buttonItems = [
        {
            type: 'icon-button' as const,
            id: 'copy-code',
            iconName: 'file' as const,
            text: 'Copy Mermaid Code',
            popoverFeedback: (
                <StatusIndicator type='success'>
                    Mermaid code copied
                </StatusIndicator>
            )
        },
        {
            type: 'icon-button' as const,
            id: 'download-png',
            iconName: 'download' as const,
            text: 'Download as PNG',
            popoverFeedback: (
                <StatusIndicator type='success'>
                    PNG downloaded
                </StatusIndicator>
            )
        }
    ];

    return (
        <div style={{ position: 'relative', margin: '12px 0' }}>
            <div style={{
                position: 'absolute',
                top: '8px',
                right: '8px',
                zIndex: 10
            }}>
                <ButtonGroup
                    onItemClick={handleButtonClick}
                    ariaLabel='Mermaid diagram actions'
                    dropdownExpandToViewport
                    items={buttonItems}
                    variant='icon'
                />
            </div>
            <div
                ref={containerRef}
                style={{
                    padding: '12px',
                    backgroundColor: '#1a1a1a',
                    border: '1px solid #333',
                    borderRadius: '4px',
                    overflow: 'auto'
                }}
                dangerouslySetInnerHTML={{ __html: svg }}
            />
        </div>
    );
});

MermaidDiagram.displayName = 'MermaidDiagram';

export default MermaidDiagram;
