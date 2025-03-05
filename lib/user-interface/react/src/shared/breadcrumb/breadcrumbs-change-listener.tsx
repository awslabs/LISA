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

import { BreadcrumbGroupProps } from '@cloudscape-design/components';
import _ from 'lodash';
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { setBreadcrumbs } from '../reducers/breadcrumbs.reducer';
import { useAppDispatch } from '../../config/store';

export const BreadcrumbsDefaultChangeListener = () => {
    const location = useLocation();
    const dispatch = useAppDispatch();

    useEffect(() => {
        const pathSegments = location.pathname.split('/').filter((segment) => segment);
        const items: BreadcrumbGroupProps.Item[] = [];

        let currentPath = '';
        pathSegments.forEach((segment) => {
            currentPath += `/${segment}`;
            const text = _.startCase(segment);
            items.push({
                text,
                href: currentPath,
            });
        });

        dispatch(setBreadcrumbs(items));
    }, [location.pathname, dispatch]);

    return null;
};

export default BreadcrumbsDefaultChangeListener;