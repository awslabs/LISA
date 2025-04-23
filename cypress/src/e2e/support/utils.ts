/**
 * The `getTopLevelDomain` function extracts the top‑level domain from a URL:
 *   • "www.example.com"      → "example.com"
 *   • "sub.example.co.uk"    → "example.co.uk"
 *
 * Using a named import:
 *   – Only the specified function is brought in (not the whole module)
 *   – Keeps your bundle smaller and your dependencies clear
 *
 * In this Cypress test file, we use `getTopLevelDomain` to parse
 * the authorization server’s base domain from an OpenID configuration URL.
 */

export const getTopLevelDomain = (url: string): string => {
    const parts = url.split('/');
    // https://<part[2]>/...
    return parts[2];
};
