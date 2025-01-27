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
import Link from '@cloudscape-design/components/link';
import { Repository } from '../types';
import { DEFAULT_PAGE_SIZE_OPTIONS } from '../../shared/preferences/common-preferences';
import { getBaseURI } from '../utils';

export const CARD_DEFINITIONS = {
    header: (repo: Repository) =>
        <Link
            href={`${getBaseURI()}#/document-library/${repo.repositoryId}`}
            fontSize='heading-m'>{repo.repositoryId}
        </Link>,
    sections: [
        {
            id: 'repositoryName',
            header: 'Name',
            content: (repo: Repository) => repo.repositoryName,
        },
        {
            id: 'repoType',
            header: 'Type',
            content: (repo: Repository) => repo.type.toString(),
        },
        {
            id: 'allowedGroups',
            header: 'Allowed Groups',
            content: (repo: Repository) => `[${repo.allowedGroups.join(', ')}]`,
        },
    ],
};

export const PAGE_SIZE_OPTIONS = DEFAULT_PAGE_SIZE_OPTIONS('Repositories');

export const VISIBLE_CONTENT_OPTIONS = [
    {
        label: 'Displayed Properties',
        options: CARD_DEFINITIONS.sections.map((c) => ({
            id: c.id,
            label: c.header,
        })),
    },
];

export const DEFAULT_PREFERENCES = {
    pageSize: PAGE_SIZE_OPTIONS[0].value,
    visibleContent: CARD_DEFINITIONS.sections.map((c) => c.id),
};
