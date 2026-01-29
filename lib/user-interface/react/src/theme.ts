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

// import { Theme } from '@cloudscape-design/components/theming';

// // ============================================================================
// // THEME VARIABLES - Edit these to customize the entire theme
// // ============================================================================

// // ----------------------------------------------------------------------------
// // TYPOGRAPHY
// // ----------------------------------------------------------------------------
// const FONT_FAMILY = 'Tahoma, \'Segoe UI\', Arial, sans-serif';  // The default font family that will be applied globally.

// // ----------------------------------------------------------------------------
// // BORDERS & SPACING
// // ----------------------------------------------------------------------------
// const BORDER_RADIUS_BUTTON = '3px';     // The border radius of buttons and segmented control's segments.
// const BORDER_RADIUS_CONTAINER = '3px';  // The border radius of containers. Also used in container-based components like table, cards, expandable section, and modal.

// // ----------------------------------------------------------------------------
// // Layout & Backgrounds
// // ----------------------------------------------------------------------------
// const LIGHT_LAYOUT_MAIN_BACKGROUND = '#ECE9D8'; // The background color of the main content area on a page.

// const DARK_LAYOUT_MAIN_BACKGROUND = '#282a36';

// // ----------------------------------------------------------------------------
// // Text Colors
// // ----------------------------------------------------------------------------
// const LIGHT_TEXT_ACCENT = '#0054E3';  // The accent text color used to guide a user (the highlighted page in side nav, active tab text, selected day in date picker, and hover state in expandable section).
// const LIGHT_TEXT_BODY = '#000000';  // The default color of non-heading text and body content (text in a paragraph tag, table cell data, form field labels and values).
// const LIGHT_TEXT_HEADING = '#000000'; // The default color for headings 2-5 (headings in containers, form sections, forms, and app layout panels).
// const LIGHT_TEXT_LINK = '#0000FF';  // The default color for links.
// const LIGHT_TEXT_LINK_HOVER = '#FF0000';  // The hover color for links.

// const DARK_TEXT_ACCENT = '#bd93f9';
// const DARK_TEXT_BODY = '#f8f8f2';
// const DARK_TEXT_HEADING = '#f8f8f2';
// const DARK_TEXT_LINK = '#8be9fd';
// const DARK_TEXT_LINK_HOVER = '#ff79c6';

// // ----------------------------------------------------------------------------
// // Primary Buttons
// // ----------------------------------------------------------------------------
// const LIGHT_BUTTON_PRIMARY_BACKGROUND = '#0054E3';  // The default background color of primary buttons.
// const LIGHT_BUTTON_PRIMARY_BACKGROUND_HOVER = '#003CC8';  // The background color of primary buttons in hover state.
// const LIGHT_BUTTON_PRIMARY_BACKGROUND_ACTIVE = '#002D96'; // The background color of primary buttons in active state.
// const LIGHT_BUTTON_PRIMARY_TEXT = '#FFFFFF';  // The default text color of primary buttons.
// const LIGHT_BUTTON_PRIMARY_TEXT_HOVER = '#FFFFFF';  // The hover text color of primary buttons.
// const LIGHT_BUTTON_PRIMARY_TEXT_ACTIVE = '#FFFFFF'; // The active text color of primary buttons.

// const DARK_BUTTON_PRIMARY_BACKGROUND = '#bd93f9';
// const DARK_BUTTON_PRIMARY_BACKGROUND_HOVER = '#ff79c6';
// const DARK_BUTTON_PRIMARY_BACKGROUND_ACTIVE = '#ff5555';
// const DARK_BUTTON_PRIMARY_TEXT = '#282a36';
// const DARK_BUTTON_PRIMARY_TEXT_HOVER = '#282a36';
// const DARK_BUTTON_PRIMARY_TEXT_ACTIVE = '#282a36';

// // ----------------------------------------------------------------------------
// // Normal/Secondary Buttons
// // ----------------------------------------------------------------------------
// const LIGHT_BUTTON_NORMAL_BACKGROUND = '#E0E0E0'; // The default background color of normal buttons.
// const LIGHT_BUTTON_NORMAL_BACKGROUND_HOVER = '#ECECEC'; // The background color of normal buttons in hover state.
// const LIGHT_BUTTON_NORMAL_BACKGROUND_ACTIVE = '#C0C0C0';  // The background color of normal buttons in active state.
// const LIGHT_BUTTON_NORMAL_TEXT = '#000000'; // The default text color of normal buttons.
// const LIGHT_BUTTON_NORMAL_TEXT_HOVER = '#000000'; // The hover text color of normal buttons.
// const LIGHT_BUTTON_NORMAL_TEXT_ACTIVE = '#000000';  // The active text color of normal buttons.
// const LIGHT_BUTTON_NORMAL_BORDER = '#ADADAD'; // The border color of normal buttons.
// const LIGHT_BUTTON_NORMAL_BORDER_HOVER = '#0054E3'; // The border color of normal buttons in hover state.
// const LIGHT_BUTTON_NORMAL_BORDER_ACTIVE = '#003CC8';  // The border color of normal buttons in active state.

// const DARK_BUTTON_NORMAL_BACKGROUND = '#44475a';
// const DARK_BUTTON_NORMAL_BACKGROUND_HOVER = '#6272a4';
// const DARK_BUTTON_NORMAL_BACKGROUND_ACTIVE = '#44475a';
// const DARK_BUTTON_NORMAL_TEXT = '#f8f8f2';
// const DARK_BUTTON_NORMAL_TEXT_HOVER = '#f8f8f2';
// const DARK_BUTTON_NORMAL_TEXT_ACTIVE = '#f8f8f2';
// const DARK_BUTTON_NORMAL_BORDER = '#6272a4';
// const DARK_BUTTON_NORMAL_BORDER_HOVER = '#bd93f9';
// const DARK_BUTTON_NORMAL_BORDER_ACTIVE = '#ff79c6';

// // ----------------------------------------------------------------------------
// // Input Fields
// // ----------------------------------------------------------------------------
// const LIGHT_INPUT_BACKGROUND = '#FFFFFF'; // The default background color of form inputs (background fill of an input, textarea, autosuggest, and trigger of a select and multiselect).
// const LIGHT_INPUT_BACKGROUND_DISABLED = '#d0d0d0';  // The background color of a disabled form input.
// const LIGHT_INPUT_BORDER = '#7F9DB9'; // The default border color of form inputs.
// const LIGHT_INPUT_BORDER_FOCUSED = '#0054E3'; // The color of focus states for form inputs.

// const DARK_INPUT_BACKGROUND = '#44475a';
// const DARK_INPUT_BACKGROUND_DISABLED = '#2e303d';
// const DARK_INPUT_BORDER = '#6272a4';
// const DARK_INPUT_BORDER_FOCUSED = '#bd93f9';

// // ----------------------------------------------------------------------------
// // Containers
// // ----------------------------------------------------------------------------
// const LIGHT_CONTAINER_CONTENT_BACKGROUND = '#F0F0F0'; // The background color of container main content areas (content areas of form sections, containers, tables, and cards).
// const LIGHT_CONTAINER_HEADER_BACKGROUND = '#0054E3';  // The background color of container headers (headers of form sections, containers, tables, and card collections).

// const DARK_CONTAINER_CONTENT_BACKGROUND = '#44475a';
// const DARK_CONTAINER_HEADER_BACKGROUND = '#282a36';

// // ----------------------------------------------------------------------------
// // Selection & Interaction
// // ----------------------------------------------------------------------------
// const LIGHT_ITEM_SELECTED_BACKGROUND = '#B6BDD2'; // The background color of a selected item (tokens, selected table rows, cards, and tile backgrounds).
// const LIGHT_ITEM_SELECTED_BORDER = '#0054E3'; // The border color of a selected item.

// const DARK_ITEM_SELECTED_BACKGROUND = '#6272a4';
// const DARK_ITEM_SELECTED_BORDER = '#bd93f9';

// // ----------------------------------------------------------------------------
// // Flashbar Notifications - flashbar visual context
// // ----------------------------------------------------------------------------
// const LIGHT_NOTIFICATION_SUCCESS_BACKGROUND = '#5eab5a';  // Background color for green notifications.
// const LIGHT_NOTIFICATION_ERROR_BACKGROUND = '#C63927';  // Background color for red notifications.
// const LIGHT_NOTIFICATION_INFO_BACKGROUND = '#0054E3'; // Background color for blue notifications.

// const DARK_NOTIFICATION_SUCCESS_BACKGROUND = '#50fa7b';
// const DARK_NOTIFICATION_ERROR_BACKGROUND = '#ff5555';
// const DARK_NOTIFICATION_INFO_BACKGROUND = '#8be9fd';

// // ----------------------------------------------------------------------------
// // Top Navigation - top-navigation visual context
// // ----------------------------------------------------------------------------
// const LIGHT_TOPNAV_BACKGROUND = '#0054E3';  // The background color of container main content areas (Top nav background).
// const LIGHT_TOPNAV_TEXT = '#FFFFFF';  // The color of clickable elements in their default state (Top nav tabs, interactive link text, and icons).
// const LIGHT_TOPNAV_TEXT_HOVER = '#FFF8DC';  // The color of clickable elements in their hover state.
// const LIGHT_TOPNAV_TEXT_ACTIVE = '#FFFFFF'; // The color of clickable elements in their active state.
// const LIGHT_TOPNAV_TITLE_TEXT = '#000000';  // The color of the title in the top navigation.
// const LIGHT_TOPNAV_DROPDOWN_BACKGROUND = '#FFFFFF'; // The default background color of dropdown items (select, multiselect, autosuggest, and datepicker dropdown backgrounds).
// const LIGHT_TOPNAV_DROPDOWN_BACKGROUND_HOVER = '#0054E3'; // The background color of dropdown items on hover (background of hovered items in select, multiselect, autosuggest, and datepicker dropdowns).
// const LIGHT_TOPNAV_DROPDOWN_BORDER = '#0054E3'; // The border color of the dropdown container (border color of the dropdown container in button dropdown, select, and multi-select).
// const LIGHT_TOPNAV_DROPDOWN_TEXT = '#000000'; // The default text color of dropdown items (label and label tag text color for autosuggest, select, and multiselect).

// const DARK_TOPNAV_BACKGROUND = '#282a36';
// const DARK_TOPNAV_TEXT = '#f8f8f2';
// const DARK_TOPNAV_TEXT_HOVER = '#bd93f9';
// const DARK_TOPNAV_TEXT_ACTIVE = '#ff79c6';
// const DARK_TOPNAV_TITLE_TEXT = '#f8f8f2';
// const DARK_TOPNAV_DROPDOWN_BACKGROUND = '#44475a';
// const DARK_TOPNAV_DROPDOWN_BACKGROUND_HOVER = '#6272a4';
// const DARK_TOPNAV_DROPDOWN_BORDER = '#bd93f9';
// const DARK_TOPNAV_DROPDOWN_TEXT = '#f8f8f2';

// // ----------------------------------------------------------------------------
// // Alert Boxes - alert visual context
// // ----------------------------------------------------------------------------
// const LIGHT_ALERT_TEXT = '#000000'; // The default color of non-heading text and body content (text in a paragraph tag, table cell data, form field labels and values).
// const LIGHT_ALERT_BACKGROUND = '#ECE9D8'; // The background color of container main content areas (content areas of form sections, containers, tables, and cards).

// const DARK_ALERT_TEXT = '#f8f8f2';
// const DARK_ALERT_BACKGROUND = '#44475a';

// // ----------------------------------------------------------------------------
// // Global Dropdowns
// // ----------------------------------------------------------------------------
// const LIGHT_DROPDOWN_BACKGROUND = '#ffffff';  // The default background color of dropdown items.
// const LIGHT_DROPDOWN_HOVER = '#0054E2'; // The background color of dropdown items on hover.
// const LIGHT_DROPDOWN_BORDER = '#0054E2';  // The border color of the dropdown container.
// const LIGHT_DROPDOWN_TEXT = '#000001';  // The default text color of dropdown items.
// const LIGHT_DROPDOWN_TEXT_HOVER = '#FFFFFf';  // The text color of hovered or selected dropdown items.
// const LIGHT_FILTER_MATCH_TEXT = '#ffffFF';  // The color of text matching a user's query.


// const DARK_DROPDOWN_BACKGROUND = '#282a36';
// const DARK_DROPDOWN_HOVER = '#6272a3';
// const DARK_DROPDOWN_BORDER = '#bd93f8';
// const DARK_DROPDOWN_TEXT = '#f8f8f2';
// const DARK_DROPDOWN_TEXT_HOVER = '#f8f8f2';
// const DARK_FILTER_MATCH_TEXT = '#ff79c6';


// // ============================================================================
// // CLOUDSCAPE DESIGN TOKENS
// // ============================================================================

// export const brandTheme: Theme = {
//     tokens: {

//         // ===================================================
//         // Dropdown Menu TOKENS - Global (not top nav)
//         // ===================================================
//         colorBackgroundDropdownItemDefault: {
//             light: LIGHT_DROPDOWN_BACKGROUND,
//             dark: DARK_DROPDOWN_BACKGROUND,
//         },

//         colorBackgroundDropdownItemHover: {
//             light: LIGHT_DROPDOWN_HOVER,
//             dark: DARK_DROPDOWN_HOVER,
//         },

//         colorBorderDropdownContainer: {
//             light: LIGHT_DROPDOWN_BORDER,
//             dark: DARK_DROPDOWN_BORDER,
//         },

//         colorBackgroundDropdownItemFilterMatch: {
//             light: LIGHT_DROPDOWN_HOVER,
//             dark: DARK_DROPDOWN_HOVER,
//         },

//         colorTextDropdownItemDefault: {
//             light: LIGHT_DROPDOWN_TEXT,
//             dark: DARK_DROPDOWN_TEXT,
//         },

//         colorTextDropdownItemHighlighted: {
//             light: LIGHT_DROPDOWN_TEXT_HOVER,
//             dark: DARK_DROPDOWN_TEXT_HOVER,
//         },

//         colorTextDropdownItemFilterMatch: {
//             light: LIGHT_FILTER_MATCH_TEXT,
//             dark: DARK_FILTER_MATCH_TEXT,
//         },

//         // ========================================
//         // TYPOGRAPHY TOKENS
//         // ========================================
//         fontFamilyBase: FONT_FAMILY,

//         // ========================================
//         // BORDER & SPACING TOKENS
//         // ========================================
//         borderRadiusButton: BORDER_RADIUS_BUTTON,
//         borderRadiusContainer: BORDER_RADIUS_CONTAINER,

//         // ========================================
//         // COLOR TOKENS - Layout & Backgrounds
//         // ========================================
//         colorBackgroundLayoutMain: {
//             light: LIGHT_LAYOUT_MAIN_BACKGROUND,
//             dark: DARK_LAYOUT_MAIN_BACKGROUND,
//         },

//         // ========================================
//         // COLOR TOKENS - Text
//         // ========================================
//         colorTextAccent: {
//             light: LIGHT_TEXT_ACCENT,
//             dark: DARK_TEXT_ACCENT,
//         },
//         colorTextBodyDefault: {
//             light: LIGHT_TEXT_BODY,
//             dark: DARK_TEXT_BODY,
//         },
//         colorTextHeadingDefault: {
//             light: LIGHT_TEXT_HEADING,
//             dark: DARK_TEXT_HEADING,
//         },
//         colorTextLinkDefault: {
//             light: LIGHT_TEXT_LINK,
//             dark: DARK_TEXT_LINK,
//         },
//         colorTextLinkHover: {
//             light: LIGHT_TEXT_LINK_HOVER,
//             dark: DARK_TEXT_LINK_HOVER,
//         },

//         // ========================================
//         // COLOR TOKENS - Buttons (Primary)
//         // ========================================
//         colorBackgroundButtonPrimaryDefault: {
//             light: LIGHT_BUTTON_PRIMARY_BACKGROUND,
//             dark: DARK_BUTTON_PRIMARY_BACKGROUND,
//         },
//         colorBackgroundButtonPrimaryHover: {
//             light: LIGHT_BUTTON_PRIMARY_BACKGROUND_HOVER,
//             dark: DARK_BUTTON_PRIMARY_BACKGROUND_HOVER,
//         },
//         colorBackgroundButtonPrimaryActive: {
//             light: LIGHT_BUTTON_PRIMARY_BACKGROUND_ACTIVE,
//             dark: DARK_BUTTON_PRIMARY_BACKGROUND_ACTIVE,
//         },
//         colorTextButtonPrimaryDefault: {
//             light: LIGHT_BUTTON_PRIMARY_TEXT,
//             dark: DARK_BUTTON_PRIMARY_TEXT,
//         },
//         colorTextButtonPrimaryHover: {
//             light: LIGHT_BUTTON_PRIMARY_TEXT_HOVER,
//             dark: DARK_BUTTON_PRIMARY_TEXT_HOVER,
//         },
//         colorTextButtonPrimaryActive: {
//             light: LIGHT_BUTTON_PRIMARY_TEXT_ACTIVE,
//             dark: DARK_BUTTON_PRIMARY_TEXT_ACTIVE,
//         },

//         // ========================================
//         // COLOR TOKENS - Buttons (Normal/Secondary)
//         // ========================================
//         colorBackgroundButtonNormalDefault: {
//             light: LIGHT_BUTTON_NORMAL_BACKGROUND,
//             dark: DARK_BUTTON_NORMAL_BACKGROUND,
//         },
//         colorBackgroundButtonNormalHover: {
//             light: LIGHT_BUTTON_NORMAL_BACKGROUND_HOVER,
//             dark: DARK_BUTTON_NORMAL_BACKGROUND_HOVER,
//         },
//         colorBackgroundButtonNormalActive: {
//             light: LIGHT_BUTTON_NORMAL_BACKGROUND_ACTIVE,
//             dark: DARK_BUTTON_NORMAL_BACKGROUND_ACTIVE,
//         },
//         colorTextButtonNormalDefault: {
//             light: LIGHT_BUTTON_NORMAL_TEXT,
//             dark: DARK_BUTTON_NORMAL_TEXT,
//         },
//         colorTextButtonNormalHover: {
//             light: LIGHT_BUTTON_NORMAL_TEXT_HOVER,
//             dark: DARK_BUTTON_NORMAL_TEXT_HOVER,
//         },
//         colorTextButtonNormalActive: {
//             light: LIGHT_BUTTON_NORMAL_TEXT_ACTIVE,
//             dark: DARK_BUTTON_NORMAL_TEXT_ACTIVE,
//         },
//         colorBorderButtonNormalDefault: {
//             light: LIGHT_BUTTON_NORMAL_BORDER,
//             dark: DARK_BUTTON_NORMAL_BORDER,
//         },
//         colorBorderButtonNormalHover: {
//             light: LIGHT_BUTTON_NORMAL_BORDER_HOVER,
//             dark: DARK_BUTTON_NORMAL_BORDER_HOVER,
//         },
//         colorBorderButtonNormalActive: {
//             light: LIGHT_BUTTON_NORMAL_BORDER_ACTIVE,
//             dark: DARK_BUTTON_NORMAL_BORDER_ACTIVE,
//         },

//         // ========================================
//         // COLOR TOKENS - Input Fields
//         // ========================================
//         colorBackgroundInputDefault: {
//             light: LIGHT_INPUT_BACKGROUND,
//             dark: DARK_INPUT_BACKGROUND,
//         },
//         colorBackgroundInputDisabled: {
//             light: LIGHT_INPUT_BACKGROUND_DISABLED,
//             dark: DARK_INPUT_BACKGROUND_DISABLED,
//         },
//         colorBorderInputDefault: {
//             light: LIGHT_INPUT_BORDER,
//             dark: DARK_INPUT_BORDER,
//         },
//         colorBorderInputFocused: {
//             light: LIGHT_INPUT_BORDER_FOCUSED,
//             dark: DARK_INPUT_BORDER_FOCUSED,
//         },

//         // ========================================
//         // COLOR TOKENS - Containers
//         // ========================================
//         colorBackgroundContainerContent: {
//             light: LIGHT_CONTAINER_CONTENT_BACKGROUND,
//             dark: DARK_CONTAINER_CONTENT_BACKGROUND,
//         },
//         colorBackgroundContainerHeader: {
//             light: LIGHT_CONTAINER_HEADER_BACKGROUND,
//             dark: DARK_CONTAINER_HEADER_BACKGROUND,
//         },

//         // ========================================
//         // COLOR TOKENS - Selection & Interaction
//         // ========================================
//         colorBackgroundItemSelected: {
//             light: LIGHT_ITEM_SELECTED_BACKGROUND,
//             dark: DARK_ITEM_SELECTED_BACKGROUND,
//         },
//         colorBorderItemSelected: {
//             light: LIGHT_ITEM_SELECTED_BORDER,
//             dark: DARK_ITEM_SELECTED_BORDER,
//         },
//     },

//     // ========================================
//     // CONTEXT-SPECIFIC OVERRIDES
//     // ========================================
//     contexts: {
//         flashbar: {
//             tokens: {
//                 colorBackgroundNotificationGreen: {
//                     light: LIGHT_NOTIFICATION_SUCCESS_BACKGROUND,
//                     dark: DARK_NOTIFICATION_SUCCESS_BACKGROUND,
//                 },
//                 colorBackgroundNotificationRed: {
//                     light: LIGHT_NOTIFICATION_ERROR_BACKGROUND,
//                     dark: DARK_NOTIFICATION_ERROR_BACKGROUND,
//                 },
//                 colorBackgroundNotificationBlue: {
//                     light: LIGHT_NOTIFICATION_INFO_BACKGROUND,
//                     dark: DARK_NOTIFICATION_INFO_BACKGROUND,
//                 },
//             },
//         },

//         'top-navigation': {
//             tokens: {
//                 colorBackgroundContainerContent: {
//                     light: LIGHT_TOPNAV_BACKGROUND,
//                     dark: DARK_TOPNAV_BACKGROUND,
//                 },
//                 colorTextInteractiveDefault: {
//                     light: LIGHT_TOPNAV_TEXT,
//                     dark: DARK_TOPNAV_TEXT,
//                 },
//                 colorTextInteractiveHover: {
//                     light: LIGHT_TOPNAV_TEXT_HOVER,
//                     dark: DARK_TOPNAV_TEXT_HOVER,
//                 },
//                 colorTextInteractiveActive: {
//                     light: LIGHT_TOPNAV_TEXT_ACTIVE,
//                     dark: DARK_TOPNAV_TEXT_ACTIVE,
//                 },
//                 colorTextTopNavigationTitle: {
//                     light: LIGHT_TOPNAV_TITLE_TEXT,
//                     dark: DARK_TOPNAV_TITLE_TEXT,
//                 },
//                 colorBackgroundDropdownItemDefault: {
//                     light: LIGHT_TOPNAV_DROPDOWN_BACKGROUND,
//                     dark: DARK_TOPNAV_DROPDOWN_BACKGROUND,
//                 },
//                 colorBackgroundDropdownItemHover: {
//                     light: LIGHT_TOPNAV_DROPDOWN_BACKGROUND_HOVER,
//                     dark: DARK_TOPNAV_DROPDOWN_BACKGROUND_HOVER,
//                 },
//                 colorBorderDropdownContainer: {
//                     light: LIGHT_TOPNAV_DROPDOWN_BORDER,
//                     dark: DARK_TOPNAV_DROPDOWN_BORDER,
//                 },
//                 colorTextDropdownItemDefault: {
//                     light: LIGHT_TOPNAV_DROPDOWN_TEXT,
//                     dark: DARK_TOPNAV_DROPDOWN_TEXT,
//                 },
//             },
//         },

//         alert: {
//             tokens: {
//                 colorTextBodyDefault: {
//                     light: LIGHT_ALERT_TEXT,
//                     dark: DARK_ALERT_TEXT,
//                 },
//                 colorBackgroundContainerContent: {
//                     light: LIGHT_ALERT_BACKGROUND,
//                     dark: DARK_ALERT_BACKGROUND,
//                 },
//             },
//         },
//     },
// };
