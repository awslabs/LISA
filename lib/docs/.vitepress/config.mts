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
import { tabsMarkdownPlugin } from 'vitepress-plugin-tabs'

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
          { text: 'Access Control', link: '/admin/getting-started#access-control' },
        ]
      },
      {
        text: 'Architecture Overview',  link: '/admin/architecture',
        items: [
          { text: 'Serve', link: '/admin/architecture#lisa-serve' },
          { text: 'MCP', link: '/admin/architecture#lisa-mcp' },
          { text: 'Chat UI', link: '/admin/architecture#chat-ui' },
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
      { text: 'API Token Management', link: '/config/api-tokens' },
      { text: 'Model Compatibility', link: '/config/model-compatibility',
        items: [
          {text: "vLLM Variables", link: '/config/vllm_variables'}
        ]
      },
      { text: 'Model Management API', link: '/config/model-management-api' },
      { text: 'Model Management UI', link: '/config/model-management-ui' },
      { text: 'Chat Assistant Stacks', link: '/config/chat-assistant-stacks' },
      { text: 'Bedrock Guardrails', link: '/config/guardrails' },
      { text: 'Usage & Features', link: '/config/usage' },
      { text: 'RAG Repository', link: '/config/repositories' },
      { text: 'Langfuse Tracing', link: '/config/langfuse-tracing'},
      { text: 'Private Labeling', link: '/config/custom-branding' },
      {
        text: 'Configuration Schema',
        link: '/config/configuration',
        items: [
          { text: 'Config Generator CLI', link: '/config/config-generator' },
          { text: 'VPC & Subnet Overrides', link: '/config/vpc-overrides' },
          { text: 'Security Group Overrides', link: '/config/security-group-overrides' },
          { text: 'Role Overrides', link: '/config/role-overrides' },
        ],
      },
      { text: 'LISA MCP: Self-host servers', link: '/config/hosted-mcp' },
      { text: 'MCP Connections: Third-party servers', link: '/config/mcp' },
      { text: 'MCP Workbench: Experimentation', link: '/config/mcp-workbench' },
      { text: 'Usage Analytics', link: '/config/cloudwatch' },
      { text: 'Claude Code Setup for LISA Serve', link: '/config/claude-code-setup' },
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
  },
  {
    text: 'API Reference',
    items: [
      { text: 'API Tokens', link: '/config/api-tokens#managing-tokens-via-api' },
      { text: 'Chat Assistant Stacks', link: '/config/chat-assistant-stacks#api-reference' },
      { text: 'Collection Management (Repository)', link: '/config/collection-management-api#endpoints' },
      { text: 'Bedrock Guardrails', link: '/config/guardrails#managing-guardrails-via-lisa-models-api' },
      { text: 'Hosted MCP Servers (/mcp)', link: '/config/hosted-mcp#api-operations' },
      { text: 'Metrics', link: '/admin/api-overview#metrics-api-gateway-endpoints' },
      { text: 'Model Management (/models)', link: '/config/model-management-api#listing-models-admin-api' },
      { text: 'RAG Repository', link: '/config/repositories#configuration-examples' },
      // TODO: Add API documentation for the following APIs
      // { text: 'MCP Workbench', link: '/config/mcp-workbench#programmatic-api-access' },
      // { text: 'Bedrock Knowledge Base (/bedrock-kb)', link: '/config/TODO-bedrock-kb#api-reference' },
      // { text: 'Configuration (/configuration)', link: '/config/TODO-configuration#api-reference' },
      // { text: 'MCP Server Connections (/mcp-server)', link: '/config/TODO-mcp-server#api-reference' },
      // { text: 'MCP Workbench tool management REST API (/mcp-workbench)', link: '/config/TODO-mcp-workbench#api-reference' },
      // { text: 'Prompt Templates (/prompt-templates)', link: '/config/TODO-prompt-templates#api-reference' },
      // { text: 'Session (/session)', link: '/config/TODO-session#api-reference' },
      // { text: 'User Preferences (/user-preferences)', link: '/config/TODO-user-preferences#api-reference' },
    ],
  },
];

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'en-US',
  title: 'LISA Documentation',
  description: 'LLM Inference Solution for Amazon Dedicated Cloud (LISA)',
  outDir: 'dist',
  base: '/LISA/',
  head: [['link', { rel: 'icon', href: '/LISA/favicon.ico' }]],
  markdown: {
    config(md) {
      md.use(tabsMarkdownPlugin)
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
