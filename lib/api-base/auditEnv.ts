import { Config } from '../schema';

export const LISA_AUDIT_ENABLED = 'LISA_AUDIT_ENABLED';
export const LISA_AUDIT_AUDIT_ALL = 'LISA_AUDIT_AUDIT_ALL';
export const LISA_AUDIT_ENABLED_PATH_PREFIXES = 'LISA_AUDIT_ENABLED_PATH_PREFIXES';
export const LISA_AUDIT_MAX_BODY_BYTES = 'LISA_AUDIT_MAX_BODY_BYTES';
export const LISA_AUDIT_INCLUDE_JSON_BODY = 'LISA_AUDIT_INCLUDE_JSON_BODY';
export const LISA_AUDIT_API_GATEWAY_BASE_PATH = 'LISA_AUDIT_API_GATEWAY_BASE_PATH';

function normalizePrefix(prefix: string): string {
    const trimmed = prefix.trim();
    if (!trimmed) return '';
    const withLeading = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    return withLeading.replace(/\/+$/, '');
}

export function getAuditLoggingEnv(config: Config): Record<string, string> {
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

