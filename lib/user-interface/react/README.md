# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
   parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: ['./tsconfig.json', './tsconfig.node.json'],
    tsconfigRootDir: __dirname,
   },
```


- Replace `plugin:@typescript-eslint/recommended` to `plugin:@typescript-eslint/recommended-type-checked` or `plugin:@typescript-eslint/strict-type-checked`
- Optionally add `plugin:@typescript-eslint/stylistic-type-checked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and add `plugin:react/recommended` & `plugin:react/jsx-runtime` to the `extends` list

## Local Development

1. Create a new file in `/lib/user-interface/react/public/env.js` with the following values: (NOTE: Replace ALL_CAP
   variables with actual values)

    ```js
    window.env = {
        'AUTHORITY': COGNITO_AUTH,
        'CLIENT_ID': COGNITOR_CLIENT_ID,
        'ADMIN_GROUP': ADMIN_GROUP,
        'JWT_GROUPS_PROP': 'cognito:groups',
        'CUSTOM_SCOPES': [],
        'RESTAPI_URI': ALB_URL,
        'RESTAPI_VERSION': 'v2',
        'RAG_ENABLED': true,
        'SYSTEM_BANNER': {
            'text': 'LISA System',
            'backgroundColor': 'orange',
            'fontColor': 'black',
        },
        'API_BASE_URL': API_GW_URL,
        'MODELS': [],
    };
    ```

2. Run `npm run dev`
