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

import { defineConfig } from 'vitepress';

const navLinks = [
  {
    text: 'System Administrator Guide',
    items: [
      {
        text: 'Getting Started', link: '/admin/getting-started',
        items: [
          { text: 'What is LISA', link: '/admin/getting-started#what-is-lisa' },
          { text: 'Major Features', link: '/admin/getting-started#major-features' },
          { text: 'Key Features & Benefits', link: '/admin/getting-started#key-features-benefits' },
        ]
      },
      {
        text: 'Architecture Overview',  link: '/admin/architecture',
        items: [
          { text: 'Serve', link: '/admin/architecture#serve' },
          { text: 'Chat UI', link: '/admin/architecture#chat-ui' },
          { text: 'Model Management', link: '/admin/architecture#model-management' },
        ],
      },
      { text: 'Deployment', link: '/admin/deploy',
      items: [
          { text: 'Prerequisites', link: '/admin/deploy#prerequisites' },
          { text: 'Software', link: '/admin/deploy#software' },
          { text: 'Deployment Steps', link: '/admin/deploy#deployment-steps' },
          { text: 'ADC Region Deployment Tips', link: '/admin/deploy#adc-region-deployment-tips' },
        ],
      },
      { text: 'Example IdP Configurations', link: '/admin/idp-config' },
      { text: 'API Overview', link: '/admin/api-overview' },
    ],
  },
  {
    text: 'Advanced Configuration',
    items: [
      { text: 'Programmatic API Tokens', link: '/config/api-tokens' },
      { text: 'Model Compatibility', link: '/config/model-compatibility' },
      { text: 'Model Management API', link: '/config/model-management-api' },
      { text: 'Model Management UI', link: '/config/model-management-ui' },
      { text: 'Usage & Features', link: '/config/usage' },
      { text: 'RAG Vector Stores', link: '/config/vector-stores' },
      {
        text: 'Configuration Schema',
        link: '/config/configuration',
        items: [
          { text: 'VPC & Subnet Overrides', link: '/config/vpc-overrides' },
          { text: 'Security Group Overrides', link: '/config/security-group-overrides' },
          { text: 'Role Overrides', link: '/config/role-overrides' },
        ],
      },
      { text: 'Model Context Protocol (MCP)', link: '/config/mcp' },
      { text: 'MCP Workbench', link: '/config/mcp-workbench' },
      { text: 'Usage Analytics', link: '/config/cloudwatch' },
    ],
  },
  {
    text: 'User Guide',
    items: [
      { text: 'LISA Chat UI', link: '/user/chat' },
      { text: 'Document Library Management', link: '/user/document-library' },
      { text: 'Model Library', link: '/user/model-library' },
      { text: 'Breaking Changes', link: '/user/breaking-changes' },
      { text: 'Change Log', link: 'https://github.com/awslabs/LISA/releases' },
    ],
  }];

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'en-US',
  title: 'LISA Documentation',
  description: 'LLM Inference Solution for Amazon Dedicated Cloud (LISA)',
  outDir: 'dist',
  base: '/LISA/',
  head: [['link', { rel: 'icon', href: '/LISA/favicon.ico' }]],
  vite: {
    build: {
      rollupOptions: {
      },
    },
  },
  // https://vitepress.dev/reference/default-theme-config
  themeConfig: {
    logo: {
      light: '/logo-light.svg',
      dark: '/logo-dark.svg',
    },
    nav: [
      { text: 'Home', link: '/' },
      ...navLinks,
    ],

    sidebar: navLinks,

    socialLinks: [
      { icon: 'github', link: 'https://github.com/awslabs/LISA' },
    ],
    search: {
      provider: 'local',
    },
  },
});
