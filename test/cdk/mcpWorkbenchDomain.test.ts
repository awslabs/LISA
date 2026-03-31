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

import { defaultMcpWorkbenchHostnameFromServeApiDomain } from '../../lib/serve/mcpWorkbenchDomain';

describe('defaultMcpWorkbenchHostnameFromServeApiDomain', () => {
    it('maps lisa-serve host to lisa-mcp-workbench (coworker case)', () => {
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('lisa-serve.evmann.people.aws.dev')).toBe(
            'lisa-mcp-workbench.evmann.people.aws.dev',
        );
    });

    it('maps first label ending with -serve', () => {
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('api-serve.example.com')).toBe('api-mcp-workbench.example.com');
    });

    it('maps bare serve label to mcp-workbench', () => {
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('serve.alias.people.aws.dev')).toBe('mcp-workbench.alias.people.aws.dev');
    });

    it('returns null when no serve pattern', () => {
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('lisa.example.com')).toBeNull();
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('myserve.example.com')).toBeNull();
    });

    it('returns null for empty input', () => {
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain(null)).toBeNull();
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain(undefined)).toBeNull();
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('')).toBeNull();
        expect(defaultMcpWorkbenchHostnameFromServeApiDomain('   ')).toBeNull();
    });
});
