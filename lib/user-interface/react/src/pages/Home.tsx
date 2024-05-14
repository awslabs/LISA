import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';

import chatImg from '../assets/chat.png';
import { Alert, Box, Button, Modal } from '@cloudscape-design/components';

export function Home({ setTools }) {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const auth = useAuth();

  useEffect(() => {
    setTools(null);
  }, [setTools]);

  useEffect(() => {
    if (auth.isAuthenticated) {
      navigate('/chatbot');
    }
    // eslint-disable-next-line
  }, [auth.isAuthenticated]);

  return (
    <Modal
      visible={!auth.isAuthenticated}
      onDismiss={() => setVisible(true)}
      header="Log in to start chatting"
      footer={
        <Box float="right">
          <Button
            onClick={() =>
              void auth.signinRedirect({
                redirect_uri: `${window.location.origin}${window.location.pathname}`,
              })
            }
            variant="primary"
          >
            Sign in
          </Button>
        </Box>
      }
    >
      {visible && <Alert type="error">You must sign in to access this page!</Alert>}
      <Box float="center">
        <div align="center">
          <figure>
            <img
              src={chatImg}
              style={{
                objectFit: 'cover',
                width: '100%',
                height: '100%',
              }}
            />
            <figcaption style={{ textAlign: 'right' }}>
              Image generated via StableDiffusion-XL on Amazon Bedrock
            </figcaption>
          </figure>
        </div>
      </Box>
    </Modal>
  );
}
export default Home;
