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

/**
 * Determines the full branding path including base URL.
 * Returns the base path for branding assets, accounting for:
 * - Vite's BASE_URL (for sub-path deployments like /lisa/)
 * - USE_CUSTOM_BRANDING setting (custom vs base branding)
 *
 */
function getBrandingPath (): string {
    const brandingDir = (window.env as any)?.USE_CUSTOM_BRANDING ? 'custom' : 'base';
    const baseUrl = import.meta.env.BASE_URL || '/';
    const normalizedBase = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;

    return `${normalizedBase}branding/${brandingDir}/`;
}

/**
 * Gets the branding asset path for the specified asset type.
 * @param asset - The asset type ('favicon', 'logo', or 'login')
 * @returns The full path to the asset, including base URL for sub-path deployments
 */
export function getBrandingAssetPath (asset: 'favicon' | 'logo' | 'login'): string {
    const basePath = getBrandingPath();

    switch (asset) {
        case 'favicon':
            return `${basePath}favicon.ico`;
        case 'logo':
            return `${basePath}logo.svg`;
        case 'login':
            return `${basePath}login.png`;
    }
}

/**
 * Gets the custom display name for branding.
 * If a custom display name is configured,
 * returns that name. Otherwise returns 'LISA' as the default.
 * @returns The display name to use throughout the application
 */
export function getDisplayName (): string {
    const customDisplayName = (window.env as any)?.CUSTOM_DISPLAY_NAME;

    return customDisplayName ? customDisplayName : 'LISA';
}
