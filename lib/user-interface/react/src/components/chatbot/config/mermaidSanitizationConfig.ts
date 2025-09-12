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

export const MERMAID_SANITIZATION_CONFIG = {
    // foreignObject Tag is necessary for text in diagrams (flow, class, etc)
    ADD_TAGS: ['foreignObject', 'p', 'br'],
    HTML_INTEGRATION_POINTS: {'foreignobject': true},
    // Various attributes that are necessary for diagram formatting
    ADD_ATTR: [
        'text-anchor', 'dominant-baseline', 'font-family', 'font-size', 'font-weight', 'font-style',
        'x', 'y', 'dx', 'dy', 'rx', 'ry', 'rotate', 'textLength', 'lengthAdjust',
        'startOffset', 'method', 'spacing', 'alignment-baseline', 'baseline-shift',
        'letter-spacing', 'word-spacing', 'text-decoration', 'text-rendering',
        'unicode-bidi', 'direction', 'writing-mode', 'glyph-orientation-vertical',
        'glyph-orientation-horizontal', 'kerning', 'fill', 'stroke', 'stroke-width',
        'opacity', 'fill-opacity', 'stroke-opacity', 'transform', 'style', 'width', 'height',
    ]
}
