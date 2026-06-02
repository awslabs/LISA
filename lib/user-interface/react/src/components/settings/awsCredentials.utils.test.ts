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

import { describe, expect, it } from 'vitest';
import { parseAwsCredentialExport } from './awsCredentials.utils';

describe('parseAwsCredentialExport', () => {
    it('parses multi-line export block with export prefix', () => {
        const text = `export ISENGARD_PRODUCTION_ACCOUNT=false
export AWS_ACCESS_KEY_ID=ASIAEXAMPLE
export AWS_SECRET_ACCESS_KEY=testing
export AWS_SESSION_TOKEN=tokenvalue`;

        expect(parseAwsCredentialExport(text)).toEqual({
            accessKeyId: 'ASIAEXAMPLE',
            secretAccessKey: 'testing', // pragma: allowlist secret
            sessionToken: 'tokenvalue',
        });
    });

    it('parses without export prefix', () => {
        const text = `AWS_ACCESS_KEY_ID=AKIAEXAMPLE
AWS_SECRET_ACCESS_KEY=testing`;

        expect(parseAwsCredentialExport(text)).toEqual({
            accessKeyId: 'AKIAEXAMPLE',
            secretAccessKey: 'testing', // pragma: allowlist secret
        });
    });

    it('parses double-quoted values', () => {
        const text = [
            'export AWS_ACCESS_KEY_ID="ASIAEXAMPLE"',
            'export AWS_SECRET_ACCESS_KEY="testing"', // pragma: allowlist secret
            'export AWS_SESSION_TOKEN="tokenvalue"',
        ].join('\n');

        expect(parseAwsCredentialExport(text)).toEqual({
            accessKeyId: 'ASIAEXAMPLE',
            secretAccessKey: 'testing', // pragma: allowlist secret
            sessionToken: 'tokenvalue',
        });
    });

    it('returns null for a single plain value', () => {
        expect(parseAwsCredentialExport('ASIAEXAMPLE')).toBeNull();
    });

    it('returns null when secret access key is missing', () => {
        expect(parseAwsCredentialExport('export AWS_ACCESS_KEY_ID=ASIAEXAMPLE')).toBeNull();
    });
});
