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

import { BreadcrumbGroup, BreadcrumbGroupProps } from '@cloudscape-design/components';
import { useNavigate } from 'react-router-dom';
import React from 'react';
import { useAppSelector } from '../../config/store';
import { selectBreadcrumbGroupItems } from '../reducers/breadcrumbs.reducer';

export const Breadcrumbs: React.FC = () => {
    const navigate = useNavigate();
    const breadcrumbs: BreadcrumbGroupProps.Item[] = useAppSelector(selectBreadcrumbGroupItems);

    return breadcrumbs?.length ?
        <BreadcrumbGroup
            items={breadcrumbs}
            ariaLabel='Breadcrumbs'
            onFollow={(event) => {
                // Prevent default behavior
                event.preventDefault();
                navigate(event.detail.href);
            }}
        /> : <></>;
};
