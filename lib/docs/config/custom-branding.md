# Custom Branding

LISA supports custom branding, allowing customers to tailor the user interface with specific logos and color schemes. This feature enables you to replace LISA branding with your organization's own branding while maintaining all functionality.

## Overview

The custom branding feature provides three key customization areas:

1. **Visual Assets** - Replace logos, favicons, and login images
2. **Display Name** - Change "LISA" brand name to your organization's product name
3. **Theme Customization** - Modify colors, fonts, and visual styling

## Configuration

### Enable Custom Branding

To enable custom branding, add these settings to your `config-custom.yaml`:

```yaml
useCustomBranding: true
customDisplayName: "YourProductName"
```

### Configuration Options

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `useCustomBranding` | boolean | No | Enables custom branding assets (logos, favicon). Default: `false` |
| `customDisplayName` | string | No | Replaces "LISA" brand name throughout the UI with your product name |

## Custom Assets

When `useCustomBranding: true` is set, LISA looks for your custom assets in the following location:

```
lib/user-interface/react/public/branding/custom/
```

### Required Asset Files

Create a `custom` directory and provide these three files:

| File | Format | Recommended Size | Purpose |
|------|--------|------------------|---------|
| `favicon.ico` | ICO | 32x32 or 16x16 | Browser tab icon |
| `logo.svg` | SVG | Vector (scalable) | Main application logo in top navigation |
| `login.png` | PNG | 400x400 or larger | Displayed on the login page |

### Directory Structure

```
lib/user-interface/react/public/branding/
├── base/              # Default LISA branding (don't modify)
│   ├── favicon.ico
│   ├── logo.svg
│   └── login.png
└── custom/            # Your custom branding (create this)
    ├── favicon.ico    # Your organization's favicon
    ├── logo.svg       # Your organization's logo
    └── login.png      # Your organization's login image
```

### Asset Guidelines

**Favicon (`favicon.ico`)**
- Standard browser icon format
- Appears in browser tabs and bookmarks
- Should be simple and recognizable at small sizes

**Logo (`logo.svg`)**
- Vector format for optimal rendering at any size
- Used in the top navigation bar
- Recommended: Display size: ~120-200px wide

**Login Image (`login.png`)**
- Displayed on the authentication page

## Display Name Customization

The `customDisplayName` setting replaces the "LISA" brand name throughout the interface, including:

- Browser page titles (e.g., "LISA Chat" → "YourProduct Chat")
- Headers and descriptions
- Welcome messages

### Example Configuration

```yaml
# config-custom.yaml
useCustomBranding: true
customDisplayName: "YourProductName"
```

With this configuration:
- The page title changes from "AWS LISA AI Chat Assistant" to "YourProductName AI Chat Assistant"
- All references to "LISA" in the UI become "YourProductName"
- Your custom logo, favicon, and login image are used

## Theme Customization

Beyond assets and names, you can customize the visual theme by creating a custom theme file that overrides the default styling.

### Theme File Location

LISA contains two theme files:

**Base Theme (Default):**
```
lib/user-interface/react/src/theme.ts
```
This file contains a minimal theme with an empty token configuration and should not be modified directly.

This theme serves as a fallback if no custom theme is defined and will load the Cloudscape default theming.

**Custom Theme (Optional):**
```
lib/user-interface/react/src/theme-custom.ts
```
Create this file to define your custom theme. This file is gitignored, allowing you to maintain organization-specific branding without committing it to version control.

When `useCustomBranding: true` is configured, LISA will automatically:
1. Look for `theme-custom.ts` first
2. Fall back to `theme.ts` if the custom file doesn't exist
3. Use Cloudscape's default theme if neither contains customizations

### Customizable Theme Elements

The [Cloudscape theming system](https://cloudscape.design/foundation/visual-foundation/theming/) allows you to customize various visual aspects of the default Cloudscape theme such as:

**Typography**
- Font families
- Font sizes and weights

**Colors**
- Background colors (layout, containers, inputs)
- Text colors (body, headings, links)
- Button colors (primary, secondary, hover states)
- Border colors
- Notification/alert colors
- Selection/highlight colors

**Layout**
- Border radius for buttons and containers
- Spacing and padding
- Component sizing

**Context-Specific Styling**
- Top navigation appearance
- Dropdown menus
- Flashbar notifications
- Alert boxes

### Theme Customization Process

1. **Create Custom Theme File**

   Copy the example custom theme to create your own:
   ```bash
   cp lib/user-interface/react/src/theme-custom.ts.example \
      lib/user-interface/react/src/theme-custom.ts
   ```

2. **Edit Theme Variables**

   Open `theme-custom.ts` and customize the theme variables at the top of the file:
   ```typescript
   // THEME VARIABLES - Edit these to customize the entire theme

   // Typography
   const FONT_FAMILY = 'YourFont, Arial, sans-serif';

   // Colors
   const LIGHT_BUTTON_PRIMARY_BACKGROUND = '#0066CC';
   const LIGHT_TEXT_LINK = '#0066CC';
   const LIGHT_TOPNAV_BACKGROUND = '#0066CC';
   // ... customize any variables you need
   ```

3. **Configure Branding**

   Enable custom branding in `config-custom.yaml`:
   ```yaml
   useCustomBranding: true
   customDisplayName: "YourProductName"
   ```

4. **Test Locally (Optional)**

   For local development testing:

   a. Update `lib/user-interface/react/public/env.js`:
   ```js
   "USE_CUSTOM_BRANDING": true,
   "CUSTOM_DISPLAY_NAME": "YourProductName"
   ```

   b. Start the development server:
   ```bash
   npm run dev
   ```

   c. The server will hot-reload as you edit `theme-custom.ts`

5. **Deploy**

   Deploy your changes:
   ```bash
   make deploy
   ```

> [!NOTE]
> During development, Vite automatically detects which theme files exist and loads the appropriate one. No build configuration changes are needed.

### Theme Application

The theme is conditionally applied based on the `useCustomBranding` setting. LISA uses Vite's glob import feature to automatically detect and load the appropriate theme file:

```typescript
// main.tsx
if (window.env?.USE_CUSTOM_BRANDING) {
    try {
        // Vite will only include files that actually exist
        const themeModules = import.meta.glob('./theme*.ts');

        // Try custom first, fall back to base
        const themeModule = themeModules['./theme-custom.ts']
            ? await themeModules['./theme-custom.ts']()
            : await themeModules['./theme.ts']();

        const { brandTheme } = themeModule;
        applyTheme({ theme: brandTheme });
        console.log('Theme loaded:', themeModules['./theme-custom.ts'] ? 'custom' : 'base');
    } catch (error) {
        console.warn('No theme file found, using Cloudscape default theme');
    }
}
```

**How it works:**
1. When `USE_CUSTOM_BRANDING` is true, LISA scans for theme files
2. If `theme-custom.ts` exists, it loads that file
3. Otherwise, it falls back to `theme.ts` (the base theme)
4. If neither file contains customizations, Cloudscape's default theme is used
5. The console logs which theme was loaded for debugging

## Implementation Details

### Asset Resolution

The branding system uses a utility function to determine asset paths:

```typescript
// From branding.ts
function getBrandingPath(): string {
    const brandingDir = window.env?.USE_CUSTOM_BRANDING ? 'custom' : 'base';
    const baseUrl = import.meta.env.BASE_URL || '/';
    return `${baseUrl}branding/${brandingDir}/`;
}
```

### Display Name Resolution

```typescript
export function getDisplayName(): string {
    const customDisplayName = window.env?.CUSTOM_DISPLAY_NAME;
    return customDisplayName ? customDisplayName : 'LISA';
}
```

These utilities ensure:
- Assets are loaded from the correct directory
- The correct display name is used throughout the application
- Fallback to default LISA branding if custom assets are missing

## Deployment Workflow

### Complete Custom Branding Setup

1. **Update Configuration**
   ```yaml
   # config-custom.yaml
   useCustomBranding: true
   customDisplayName: "YourProductName"
   ```

2. **Create Custom Assets Directory**
   ```bash
   mkdir -p lib/user-interface/react/public/branding/custom
   ```

3. **Add Your Assets**
   ```bash
   # Copy your branded assets
   cp /path/to/your/favicon.ico lib/user-interface/react/public/branding/custom/
   cp /path/to/your/logo.svg lib/user-interface/react/public/branding/custom/
   cp /path/to/your/login.png lib/user-interface/react/public/branding/custom/
   ```

4. **Customize Theme (Optional)**
   ```bash
   # Create and edit theme-custom.ts with your color scheme
   cp lib/user-interface/react/src/theme-custom.ts.example \
      lib/user-interface/react/src/theme-custom.ts

   # Edit the file to customize colors and styling
   # lib/user-interface/react/src/theme-custom.ts
   ```

5. **Deploy**
   ```bash
   make deploy
   ```

### Verification

After deployment, verify your branding:

1. **Check Browser Tab**
   - Should show your custom favicon
   - Page title should use your custom display name

2. **Check Navigation**
   - Top navigation should display your custom logo
   - Product name should appear where "LISA" previously appeared

3. **Check Login Page**
   - Should display your custom login image

4. **Check Theme (if customized)**
   - Verify colors, fonts, and styling match your specifications

## Troubleshooting

### Assets Not Loading

**Issue**: Custom assets don't appear after deployment

**Solutions**:
- Verify files exist in `lib/user-interface/react/public/branding/custom/`
- Check file names match exactly: `favicon.ico`, `logo.svg`, `login.png`
- Ensure `useCustomBranding: true` in config
- Clear browser cache and refresh
- Check browser console for errors

### Display Name Not Changing

**Issue**: "LISA" still appears instead of custom name

**Solutions**:
- Verify `customDisplayName` is set in `config-custom.yaml`
- Ensure config changes were deployed
- Check `{LISA_URL}/{STAGE}/env.js` path for `CUSTOM_DISPLAY_NAME` and `USE_CUSTOM_BRANDING`
- Redeploy the application

### Theme Not Applied

**Issue**: Custom theme colors don't appear

**Solutions**:
- Verify `useCustomBranding: true` (theme is only applied when branding is enabled)
- Ensure `theme-custom.ts` exists in `lib/user-interface/react/src/`
- Verify theme variables are properly defined in `theme-custom.ts`
- Check browser console to see which theme was loaded (`custom` or `base`)
- Rebuild the web application: `npm run build -w lisa-web`
- Clear browser cache and hard refresh
- Check browser console for errors

**Issue**: Changes to theme-custom.ts not appearing

**Solutions**:
- Restart the development server (`npm run dev`)
- Clear browser cache
- Check for TypeScript errors in the theme file
- Ensure the file is saved before refreshing

### Partial Branding

**Issue**: Some assets are custom, others are default

**Solutions**:
- Ensure all three asset files are present in the `custom` directory
- Check file permissions are readable
- Verify no typos in file names (case-sensitive on Linux)
- Review deployment logs for asset copying errors

### Theme Colors are Incorrect

**Issue**: Some components are not showing the color they were configured with in `theme-custom.ts`

**Solutions**:
- Restart the development server
- Clear browser cache
- Change the value of the component (e.g. `#0054E3` -> `#0054E2`). Reuse of the same values can occasionally be problematic in the Cloudscape theming system.
- Verify the correct token name is being used (refer to [Cloudscape theming docs](https://cloudscape.design/foundation/visual-foundation/theming/))
- Check browser console for theme loading confirmation

## Example: Complete Setup

Here's a complete example showing all aspects of custom branding:

### config-custom.yaml
```yaml
accountNumber: 123456789012
region: us-east-1
deploymentName: ACME-AI
s3BucketModels: acme-ai-models

# Custom branding configuration
useCustomBranding: true
customDisplayName: "Acme"

# Other configuration...
authConfig:
  authority: https://auth.example.com
  clientId: your-client-id
  adminGroup: acme-admins
  jwtGroupsProperty: cognito:groups
```

### Assets Prepared
```
lib/user-interface/react/public/branding/custom/
├── favicon.ico      # Acme company icon
├── logo.svg         # Acme company logo
└── login.png        # Acme branded welcome image
```

### Custom Theme
```typescript
// lib/user-interface/react/src/theme-custom.ts (excerpt)
const FONT_FAMILY = 'Roboto, Arial, sans-serif';
const LIGHT_BUTTON_PRIMARY_BACKGROUND = '#0A3D62';  // Acme blue
const LIGHT_TEXT_LINK = '#0A3D62';
const LIGHT_TOPNAV_BACKGROUND = '#0A3D62';
// ... more customizations
```

### Result
After deployment, users see:
- Browser tab: "Acme AI Chat Assistant" with Acme favicon
- Top navigation: Acme logo and "Acme" branding
- Login page: Acme welcome image
- UI theme: Acme's corporate blue color scheme
- All text references use "Acme" instead of "LISA"
