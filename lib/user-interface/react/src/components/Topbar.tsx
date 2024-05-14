import { useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { useNavigate, useHref } from 'react-router-dom';
import { applyMode, applyDensity, Density, Mode } from '@cloudscape-design/global-styles';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import { getBaseURI } from './utils';

applyDensity(Density.Comfortable);

function Topbar() {
  const navigate = useNavigate();
  const auth = useAuth();

  const [isDarkMode, setIsDarkMode] = useState(window.matchMedia('(prefers-color-scheme: dark)').matches);

  useEffect(() => {
    if (isDarkMode) {
      applyMode(Mode.Dark);
    } else {
      applyMode(Mode.Light);
    }
  }, [isDarkMode]);

  useEffect(() => {
    // Check to see if Media-Queries are supported
    if (window.matchMedia) {
      // Check if the dark-mode Media-Query matches
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        // Dark
        applyMode(Mode.Dark);
      } else {
        // Light
        applyMode(Mode.Light);
      }
    } else {
      // Default (when Media-Queries are not supported)
    }
  }, []);

  return (
    <TopNavigation
      identity={{
        href: useHref('/'),
        logo: {
          src: `${getBaseURI()}logo.png`,
          alt: 'AWS LISA Sample',
        },
      }}
      utilities={[
        {
          type: 'button',
          variant: 'link',
          text: `Chatbot`,
          disableUtilityCollapse: false,
          external: false,
          onClick: () => {
            navigate('/chatbot');
          },
        },
        {
          type: 'menu-dropdown',
          description: auth.isAuthenticated ? auth.user?.profile.email : undefined,
          onItemClick: async (item) => {
            switch (item.detail.id) {
              case 'signin':
                auth.signinRedirect({ redirect_uri: window.location.toString() });
                break;
              case 'signout':
                await auth.signoutSilent();
                break;
              default:
                break;
            }
          },
          iconName: 'user-profile',
          items: [auth.isAuthenticated ? { id: 'signout', text: 'Sign out' } : { id: 'signin', text: 'Sign in' }],
        },
        {
          type: 'button',
          iconSvg: !isDarkMode ? (
            <svg
              width="24"
              height="24"
              stroke-width="1.5"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {' '}
              <path
                d="M3 11.5066C3 16.7497 7.25034 21 12.4934 21C16.2209 21 19.4466 18.8518 21 15.7259C12.4934 15.7259 8.27411 11.5066 8.27411 3C5.14821 4.55344 3 7.77915 3 11.5066Z"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                fill="white"
              ></path>{' '}
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              className="bi bi-sun"
              viewBox="0 0 16 16"
            >
              {' '}
              <path
                d="M8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm0 1a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0zm0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13zm8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5zM3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8zm10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0zm-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0zm9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707zM4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708z"
                fill="white"
              ></path>{' '}
            </svg>
          ),
          disableUtilityCollapse: false,
          onClick: () => {
            setIsDarkMode(!isDarkMode);
          },
        },
      ]}
    />
  );
}

export default Topbar;
