import { AuthProviderProps } from 'react-oidc-context';

export const OidcConfig: AuthProviderProps = {
  authority: window.env.AUTHORITY,
  client_id: window.env.CLIENT_ID,
  redirect_uri: window.location.toString(),
  post_logout_redirect_uri: window.location.toString(),
  scope: 'openid profile email',
  onSigninCallback: async () => {
    window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
  },
};
