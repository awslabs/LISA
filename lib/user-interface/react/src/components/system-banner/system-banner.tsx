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
import { useGetConfigurationQuery } from '../../shared/reducers/configuration.reducer';

type BannerOptions = {
    position: 'TOP' | 'BOTTOM';
};

export const SystemBanner = ({ position }: BannerOptions) => {
    const { data: config } = useGetConfigurationQuery("global", {refetchOnMountOrArgChange: 5});
    const bannerStyle: React.CSSProperties = {
        width: '100%',
        position: 'fixed',
        zIndex: 4999,
        textAlign: 'center',
        padding: '2px 0px',
        backgroundColor: config[0]?.configuration.systemBanner.backgroundColor,
        color: config[0]?.configuration.systemBanner.textColor,
    };

    if (position === 'TOP') {
        bannerStyle.top = 0;
    } else {
        bannerStyle.bottom = 0;
    }

    return (
        <TextContent>
            <div style={bannerStyle} id={position === 'TOP' ? 'topBanner' : 'bottomBanner'}>
                <span><b>{config[0]?.configuration.systemBanner.text}</b></span>
            </div>
        </TextContent>
    );
};

export default SystemBanner;
