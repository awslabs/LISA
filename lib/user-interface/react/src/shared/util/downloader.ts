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

/**
 * Download a file using hidden link
 * @param url
 * @param filename
 */
export function downloadFile (url: string, filename: string) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'download';
    link.hidden = true;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Convert an SVG element to PNG and download it
 * @param svgElement - The SVG element to convert
 * @param filename - The filename for the downloaded PNG (default: 'diagram.png')
 */
export function downloadSvgAsPng (svgElement: SVGElement, filename = 'diagram.png') {
    try {
        // Get dimensions from SVG - use existing dimensions or fallback
        const parseSize = (value: string | null): number => {
            if (!value) return 0;
            return parseFloat(value.replace(/[^\d.]/g, ''));
        };

        // Try to get dimensions from SVG attributes first
        let width = parseSize(svgElement.getAttribute('width'));
        let height = parseSize(svgElement.getAttribute('height'));

        // Single fallback: use viewBox if no width/height
        if (!width || !height) {
            const viewBox = svgElement.getAttribute('viewBox');
            if (viewBox) {
                const viewBoxValues = viewBox.split(/\s+/);
                if (viewBoxValues.length >= 4) {
                    width = parseFloat(viewBoxValues[2]) || 800;
                    height = parseFloat(viewBoxValues[3]) || 600;
                }
            } else {
                // Final fallback
                width = 800;
                height = 600;
            }
        }

        // Scale factor for higher quality
        const scale = 2;

        // Clone the SVG without modifying dimensions - preserve original
        const svgClone = svgElement.cloneNode(true) as SVGElement;
        const svgString = new XMLSerializer().serializeToString(svgClone);
        const svgDataUrl = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgString)));

        const img = new Image();
        img.onload = function () {
            const canvas = document.createElement('canvas');
            // Set canvas size once - scaled for quality
            canvas.width = width * scale;
            canvas.height = height * scale;

            const ctx = canvas.getContext('2d');
            if (ctx) {
                // High quality rendering
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';

                // Draw the image at full canvas size (already scaled)
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                const pngUrl = canvas.toDataURL('image/png', 1.0);
                downloadFile(pngUrl, filename);
            }
        };
        img.src = svgDataUrl;
    } catch (err) {
        console.error('Failed to download SVG as PNG:', err);
    }
}
