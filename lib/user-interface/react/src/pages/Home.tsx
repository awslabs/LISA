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

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';

import { Alert, Box, Button, Modal } from '@cloudscape-design/components';
import { getBrandingAssetPath } from '../shared/util/branding';

export function Home ({ setNav }) {
    const navigate = useNavigate();
    const [visible, setVisible] = useState(false);
    const auth = useAuth();

    useEffect(() => {
        setNav(null);
    }, [setNav]);

    useEffect(() => {
        if (auth.isAuthenticated) {
            navigate('/ai-assistant');
        }
    // eslint-disable-next-line
  }, [auth.isAuthenticated]);

    return (
        <Modal
            visible={!auth.isAuthenticated && !auth.isLoading}
            onDismiss={() => setVisible(true)}
            header='Log in to start chatting'
            footer={
                <Box float='right'>
                    <Button
                        onClick={() =>
                            void auth.signinRedirect({
                                redirect_uri: `${window.location.origin}${window.location.pathname}`,
                            })
                        }
                        variant='primary'
                    >
                        Sign in
                    </Button>
                </Box>
            }
        >
            {visible && <Alert type='error'>You must sign in to access this page!</Alert>}
            <Box>
                <div>
                    <figure>
                        <img
                            src={getBrandingAssetPath('login')}
                            style={{
                                objectFit: 'cover',
                                width: '100%',
                                height: '100%',
                            }}
                        />
                    </figure>
                </div>
            </Box>
        </Modal>
    );
}
export default Home;
