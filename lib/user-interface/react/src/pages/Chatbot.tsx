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

import { useParams, useNavigate } from 'react-router-dom';

import { useCallback, useEffect, useState } from 'react';

import Chat from '../components/chatbot/Chat';
import Sessions from '../components/chatbot/components/Sessions';
import { useAppDispatch } from '@/config/store';
import { sessionApi } from '@/shared/reducers/session.reducer';

export function Chatbot ({ setNav }) {
    const { sessionId } = useParams();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const [key, setKey] = useState(() => new Date().toISOString());

    const handleNewSession = useCallback(() => {
        // Clear specific cached session data that might interfere with new session creation
        if (sessionId) {
            dispatch(sessionApi.util.invalidateTags([{ type: 'session', id: sessionId }]));
        }

        // Force a key update to remount the Chat component
        setKey(new Date().toISOString());

        // Navigate to clear the sessionId from URL
        navigate('/ai-assistant', { replace: true });
    }, [navigate, dispatch, sessionId]);



    useEffect(() => {
        setNav(<Sessions newSession={handleNewSession} />);
    }, [setNav, handleNewSession]);

    return <Chat key={key} sessionId={sessionId} />;
}
export default Chatbot;
