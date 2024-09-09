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

import { TextContent } from '@cloudscape-design/components';
import React from 'react';

type BannerOptions = {
    position: 'TOP' | 'BOTTOM';
};

export const SystemBanner = ({ position }: BannerOptions) => {
    const bannerStyle: React.CSSProperties = {
        width: '100%',
        position: 'fixed',
        zIndex: 4999,
        textAlign: 'center',
        padding: '2px 0px',
        backgroundColor: window.env.SYSTEM_BANNER.backgroundColor,
        color: window.env.SYSTEM_BANNER.fontColor,
    };

    if (position === 'TOP') {
        bannerStyle.top = 0;
    } else {
        bannerStyle.bottom = 0;
    }

    return (
        <TextContent>
            <div style={bannerStyle} id={position === 'TOP' ? 'topBanner' : 'bottomBanner'}>
                <span>{window.env.SYSTEM_BANNER.text}</span>
            </div>
        </TextContent>
    );
};

export default SystemBanner;
