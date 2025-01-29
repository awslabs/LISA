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

import { BreadcrumbGroup } from '@cloudscape-design/components';
import { useLocation, useNavigate } from 'react-router-dom';
import React from 'react';
import _ from 'lodash';

type BreadcrumbItem = {
    text: string;
    href: string;
};

export const Breadcrumbs: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const getBreadcrumbItems = (): BreadcrumbItem[] => {
        const pathSegments = location.pathname.split('/').filter((segment) => segment);
        const items: BreadcrumbItem[] = [];

        let currentPath = '';
        pathSegments.forEach((segment) => {
            currentPath += `/${segment}`;
            const text = _.startCase(segment);
            items.push({
                text,
                href: currentPath,
            });
        });

        return items;
    };

    return (
        <BreadcrumbGroup
            items={getBreadcrumbItems()}
            ariaLabel='Breadcrumbs'
            onFollow={(event) => {
                // Prevent default behavior
                event.preventDefault();
                navigate(event.detail.href);
            }}
        />
    );
};
