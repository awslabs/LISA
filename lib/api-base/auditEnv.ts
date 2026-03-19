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

import { Config } from '../schema';

export const LISA_AUDIT_ENABLED = 'LISA_AUDIT_ENABLED';
export const LISA_AUDIT_AUDIT_ALL = 'LISA_AUDIT_AUDIT_ALL';
export const LISA_AUDIT_ENABLED_PATH_PREFIXES = 'LISA_AUDIT_ENABLED_PATH_PREFIXES';
export const LISA_AUDIT_MAX_BODY_BYTES = 'LISA_AUDIT_MAX_BODY_BYTES';
export const LISA_AUDIT_INCLUDE_JSON_BODY = 'LISA_AUDIT_INCLUDE_JSON_BODY';
export const LISA_AUDIT_API_GATEWAY_BASE_PATH = 'LISA_AUDIT_API_GATEWAY_BASE_PATH';

function normalizePrefix (prefix: string): string {
    const trimmed = prefix.trim();
    if (!trimmed) return '';
    const withLeading = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    return withLeading.replace(/\/+$/, '');
}

export function getAuditLoggingEnv (config: Config): Record<string, string> {
    const audit = config.auditLoggingConfig;
    const enabled = audit?.enabled ?? false;
    const all = enabled && (audit?.auditAll ?? false);
    const enabledPaths = (audit?.enabledPaths ?? []).map(normalizePrefix).filter(Boolean);
    const maxBytes = audit?.maxRequestBodyBytes ?? 20000;
    const includeJsonBody = enabled && (audit?.includeJsonBody ?? false);

    return {
        [LISA_AUDIT_ENABLED]: String(enabled),
        [LISA_AUDIT_AUDIT_ALL]: String(all),
        [LISA_AUDIT_ENABLED_PATH_PREFIXES]: enabledPaths.join(','),
        [LISA_AUDIT_MAX_BODY_BYTES]: String(maxBytes),
        [LISA_AUDIT_INCLUDE_JSON_BODY]: String(includeJsonBody),
    };
}
