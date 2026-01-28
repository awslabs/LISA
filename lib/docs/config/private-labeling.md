# Private labeling

LISA supports comprehensive private labeling capabilities, allowing organizations to customize the user interface with their own logos and color schemes. This feature enables you to replace LISA branding with your organization's own branding while maintaining all functionality.

## Overview

The private labeling feature provides three key customization areas:

1. **Visual Assets** - Replace logos, favicons, and login images
2. **Display Name** - Change "LISA" to your organization's product name
3. **Theme Customization** - Modify colors, fonts, and visual styling

## Configuration

### Enable Custom Branding

To enable private labeling, add these settings to your `config-custom.yaml`:

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
- Should work on both light and dark backgrounds
- Recommended: Keep it horizontal/landscape oriented
- Recommended: Display size: ~120-200px wide

**Login Image (`login.png`)**
- Displayed on the authentication page
- Recommended: Square or vertical orientation

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

Beyond assets and names, you can customize the visual theme by creating and modifying the `theme.ts` file.

### Theme File Location

The `theme.ts` file should be created in the following path:

```
lib/user-interface/react/src/theme.ts
```

An example theme is provided at:
```
lib/user-interface/react/src/example_theme.ts
```

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

1. **Clone the Example Theme**
   ```bash
   cp lib/user-interface/react/src/example_theme.ts lib/user-interface/react/src/theme.ts
   ```

2. **Update env.js:**
   Add the following lines to the end of your `lib/user-interface/react/public/env.js` file
   ```js
   "USE_CUSTOM_BRANDING": true,
   "USE_CUSTOM_DISPLAY_NAME": "YourProductName"
   ```

3. **Start the Local Development Server**
   ```bash
   npm run dev
   ```

4. **Edit Theme Variables:**
   Open `theme.ts` and modify the variables at the top of the file:
   ```typescript
   // THEME VARIABLES - Edit these to customize
   const FONT_FAMILY = 'YourFont, Arial, sans-serif';
   const LIGHT_BUTTON_PRIMARY_BACKGROUND = '#0066CC';
   const LIGHT_TEXT_LINK = '#0066CC';
   // ... etc
   ```

5. **Save Changes:** Upon saving changes the server should reload to show your modifications

> [!TIP]
> The above local development workflow works for testing logos and branding name modifications

### Theme Application

The theme is conditionally applied based on the `useCustomBranding` setting contained within `config-custom.yaml`:

```typescript
// main.tsx
if (window.env?.USE_CUSTOM_BRANDING) {
    const { brandTheme } = await import('./theme');
    applyTheme({ theme: brandTheme });
}
```

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

### Complete private labeling Setup

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
   cp lib/user-interface/react/src/example_theme.ts lib/user-interface/react/src/theme.ts
   # Edit theme.ts with your color scheme
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
- Ensure `theme.ts` file exists (not just `example_theme.ts`)
- Rebuild the web application: `npm run build -w lisa-web`
- Clear browser cache
- Check browser console for errors

### Partial Branding

**Issue**: Some assets are custom, others are default

**Solutions**:
- Ensure all three asset files are present in the `custom` directory
- Check file permissions are readable
- Verify no typos in file names (case-sensitive on Linux)
- Review deployment logs for asset copying errors

### Theme Colors are Incorrect

**Issue**: Some components are not showing the color they were configured with in `theme.ts`

**Solutions**:
- Restart the development server
- Clear browser cache
- Change the value of the component (e.g. `#0054E3` -> `#0054E2`). Reuse of the same values seems, to occasionally, be problematic in the Cloudscape theming system.

## Example: Complete Setup

Here's a complete example showing all aspects of private labeling:

### config-custom.yaml
```yaml
accountNumber: 123456789012
region: us-east-1
deploymentName: ACME-AI
s3BucketModels: acme-ai-models

# Private labeling configuration
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
// lib/user-interface/react/src/theme.ts (excerpt)
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
