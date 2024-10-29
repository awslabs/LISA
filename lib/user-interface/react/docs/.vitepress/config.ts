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
      { text: 'Architecture Overview', link: '/admin/architecture' },
      { text: 'Lisa Components', link: '/admin/components' },
      { text: 'Getting Started', link: '/admin/getting-started' },
      { text: 'Configure IdP: Cognito & Keycloak Examples', link: '/admin/idp' },
      { text: 'Deployment', link: '/admin/deploy' },
      { text: 'Setting Model Management Admin Group', link: '/admin/model-management' },
      { text: 'LiteLLM', link: '/admin/lite-llm' },
      { text: 'API Overview', link: '/admin/api' },
      { text: 'API Request Error Handling', link: '/admin/error' },
      { text: 'Security', link: '/admin/security' },
    ],
  },
  {
    text: 'Advanced Configuration',
    items: [
      { text: 'Programmatic API Tokens', link: '/config/api-tokens' },
      { text: 'Model Compatibility', link: '/config/model-compatibility' },
      { text: 'Model Management API', link: '/config/model-management-api' },
      { text: 'Model Management UI', link: '/config/model-management-ui' },
      { text: 'Rag Vector Stores', link: '/config/vector-stores' },
      { text: 'Usage & Features', link: '/config/features' },
      { text: 'Branding', link: '/config/branding' },
      { text: 'Hiding Advanced Chat UI Components', link: '/config/hiding-chat-components' },
    ],
  },
  {
    text: 'User Guide',
    items: [
      { text: 'LISA Chat UI', link: '/user/chat' },
      { text: 'RAG', link: '/user/rag' },
      { text: 'Context Windows', link: '/user/context-windows' },
      { text: 'Model KWARGS', link: '/user/model-kwargs' },
      { text: 'Non-RAG in Context File Management', link: '/user/nonrag-management' },
      { text: 'Prompt Engineering', link: '/user/prompt-engineering' },
      { text: 'Session History', link: '/user/history' },
    ],
  }];

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'en-US',
  title: 'LISA Documentation',
  description: 'LLM Inference Solution for Amazon Dedicated Cloud (LISA)',
  outDir: '../dist/docs',
  base: '/lisa/',
  head: [['link', { rel: 'icon', href: '/lisa/assets/favicon.ico' }]],
  // https://vitepress.dev/reference/default-theme-config
  themeConfig: {
    logo: '/assets/logo.png',
    nav: [
      { text: 'Home', link: '/' },
      ...navLinks,
    ],

    sidebar: navLinks,

    socialLinks: [
      { icon: 'github', link: 'https://github.com/awslabs/lisa' },
    ],
    search: {
      provider: 'local',
    },
  },
});
