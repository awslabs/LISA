// es-lint-disable
import { AuthProvider } from 'react-oidc-context';
import App from '../App';

import { OidcConfig } from '../config/oidc.config';

function AppConfigured() {
  return (
    <AuthProvider {...OidcConfig}>
      <App />
    </AuthProvider>
  );
}

export default AppConfigured;
