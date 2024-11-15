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
      { text: 'What is Lisa?', link: '/admin/overview' },
      { text: 'Architecture Overview', link: '/admin/architecture' },
      { text: 'Getting Started', link: '/admin/getting-started' },
      { text: 'Deployment', link: '/admin/deploy' },
      { text: 'Model Management API Usage', link: '/admin/model-management' },
      { text: 'Chat UI Configuration', link: '/admin/ui-configuration' },
      { text: 'API Request Error Handling', link: '/admin/error' },
    ],
  },
  {
    text: 'Advanced Configuration',
    items: [
      { text: 'Configuration Schema', link: '/config/configuration' },
      { text: 'Model Compatibility', link: '/config/model-compatibility' },
      { text: 'Rag Vector Stores', link: '/config/vector-stores' },
      { text: 'Configure IdP: Cognito & Keycloak Examples', link: '/config/idp' },
      { text: 'LiteLLM', link: '/config/lite-llm' },
    ],
  },
  {
    text: 'User Guide',
    items: [
      { text: 'LISA Chat UI', link: '/user/chat' },
      { text: 'RAG', link: '/user/rag' },
      { text: 'Context Windows', link: '/user/context-windows' },
      { text: 'Model KWARGS', link: '/user/model-kwargs' },
      { text: 'Model Management UI', link: '/user/model-management-ui' },
      { text: 'Non-RAG in Context File Management', link: '/user/nonrag-management' },
      { text: 'Prompt Engineering', link: '/user/prompt-engineering' },
      { text: 'Session History', link: '/user/history' },
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
