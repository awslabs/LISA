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

import { ReactElement, useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useHref, useNavigate } from 'react-router-dom';
import { applyDensity, applyMode, Density, Mode } from '@cloudscape-design/global-styles';
import TopNavigation, { TopNavigationProps } from '@cloudscape-design/components/top-navigation';
import { getBaseURI } from './utils';
import { purgeStore, useAppSelector } from '../config/store';
import { selectCurrentUserIsAdmin } from '../shared/reducers/user.reducer';
import { IConfiguration } from '../shared/model/configuration.model';
import { ButtonDropdownProps } from '@cloudscape-design/components';

applyDensity(Density.Comfortable);

export type TopbarProps = {
    configs?: IConfiguration
};

function Topbar ({ configs }: TopbarProps): ReactElement {
    const navigate = useNavigate();
    const auth = useAuth();
    const isUserAdmin = useAppSelector(selectCurrentUserIsAdmin);
    const [isDarkMode, setIsDarkMode] = useState(window.matchMedia('(prefers-color-scheme: dark)').matches);

    useEffect(() => {
        if (isDarkMode) {
            applyMode(Mode.Dark);
        } else {
            applyMode(Mode.Light);
        }
    }, [isDarkMode]);

    useEffect(() => {
    // Check to see if Media-Queries are supported
        if (window.matchMedia) {
            // Check if the dark-mode Media-Query matches
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                // Dark
                applyMode(Mode.Dark);
            } else {
                // Light
                applyMode(Mode.Light);
            }
        } else {
            // Default (when Media-Queries are not supported)
        }
    }, []);

    const libraryItems = [
        ...(configs?.configuration.enabledComponents?.showRagLibrary ? [{
            id: 'document-library',
            type: 'button',
            variant: 'link',
            text: 'Document Library',
            disableUtilityCollapse: false,
            external: false,
            href: '/document-library',
        } as ButtonDropdownProps.Item] : []),
        ...(configs?.configuration.enabledComponents?.showPromptTemplateLibrary ? [{
            id: 'prompt-template',
            type: 'button',
            variant: 'link',
            text: 'Prompt Library',
            disableUtilityCollapse: false,
            external: false,
            href: '/prompt-templates',
        } as ButtonDropdownProps.Item] : []),
        {
            id: 'mcp-connection',
            type: 'button',
            variant: 'link',
            text: 'MCP Connections',
            disableUtilityCollapse: false,
            external: false,
            href: '/mcp-connections',
        },
    ];

    return (
        <TopNavigation
            identity={{
                href: useHref('/'),
                logo: {
                    src: `${getBaseURI()}logo.svg`,
                    alt: 'AWS LISA Sample',
                },
            }}
            utilities={[
                {
                    type: 'button',
                    variant: 'link',
                    text: 'AI Assistant',
                    disableUtilityCollapse: false,
                    external: false,
                    onClick: () => {
                        navigate('/ai-assistant');
                    },
                },
                ...(
                    libraryItems.length ? [{
                        type: 'menu-dropdown',
                        text: 'Libraries',
                        onItemClick: (event) => {
                            event.preventDefault();
                            navigate(event.detail.href);
                        },
                        items: libraryItems
                    }] as TopNavigationProps.Utility[] : []
                ),
                ...((isUserAdmin
                    ? [{
                        type: 'menu-dropdown',
                        text: 'Administration',
                        onItemClick: (event) => {
                            event.preventDefault();
                            navigate(event.detail.href);
                        },
                        items: [
                            {
                                id: 'configuration',
                                type: 'button',
                                variant: 'link',
                                text: 'Configuration',
                                disableUtilityCollapse: false,
                                external: false,
                                href: '/configuration',
                            } as ButtonDropdownProps.Item,
                            {
                                id: 'model-management',
                                type: 'button',
                                variant: 'link',
                                text: 'Model Management',
                                disableUtilityCollapse: false,
                                external: false,
                                href: '/model-management',
                            } as ButtonDropdownProps.Item
                        ]
                    }] : []) as TopNavigationProps.Utility[]),
                {
                    type: 'menu-dropdown',
                    description: auth.isAuthenticated ? auth.user?.profile.email : undefined,
                    onItemClick: async (item) => {
                        switch (item.detail.id) {
                            case 'signin':
                                auth.signinRedirect({ redirect_uri: window.location.toString() });
                                break;
                            case 'signout':
                                await purgeStore();
                                await auth.signoutSilent();
                                break;
                            case 'color-mode':
                                setIsDarkMode(!isDarkMode);
                                break;
                            default:
                                break;
                        }
                    },
                    iconName: 'user-profile',
                    items: [
                        { id: 'version-info', text: `LISA v${window.gitInfo?.revisionTag}`, disabled: true },
                        { id: 'color-mode', text: isDarkMode ? 'Light mode' : 'Dark mode', iconSvg: (
                            <svg
                                width='24'
                                height='24'
                                strokeWidth='1.5'
                                viewBox='0 0 24 24'
                                fill='none'
                                xmlns='http://www.w3.org/2000/svg'
                            >
                                {' '}
                                <path
                                    d='M3 11.5066C3 16.7497 7.25034 21 12.4934 21C16.2209 21 19.4466 18.8518 21 15.7259C12.4934 15.7259 8.27411 11.5066 8.27411 3C5.14821 4.55344 3 7.77915 3 11.5066Z'
                                    stroke='currentColor'
                                    strokeLinecap='round'
                                    strokeLinejoin='round'
                                    fill='white'
                                ></path>
                                {' '}
                            </svg>
                        )
                        },
                        auth.isAuthenticated ? { id: 'signout', text: 'Sign out' } : { id: 'signin', text: 'Sign in' },
                    ],
                }
            ]}
        />
    );
}

export default Topbar;
