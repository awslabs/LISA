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

import { useParams, useNavigate, useLocation } from 'react-router-dom';

import { useCallback, useEffect } from 'react';

import Chat from '../components/chatbot/Chat';
import Sessions from '../components/chatbot/components/Sessions';
import { useAppDispatch } from '@/config/store';
import { sessionApi } from '@/shared/reducers/session.reducer';

export function Chatbot ({ setNav }) {
    const { sessionId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const dispatch = useAppDispatch();
    const initialStack = location.state?.stack;

    // Same "clean" key whenever there's no session ID: refresh at /ai-assistant (or /ai-assistant/) and clicking New
    // both get key 'new', so Chat remounts and useSession runs createNewSession() (clears assistant).
    const hasSessionInUrl = sessionId != null && sessionId !== '';
    const chatKey = hasSessionInUrl ? sessionId : (initialStack ? `stack-${initialStack.stackId}` : 'new');

    const handleNewSession = useCallback(() => {
        // Clear specific cached session data that might interfere with new session creation
        if (sessionId) {
            dispatch(sessionApi.util.invalidateTags([{ type: 'session', id: sessionId }]));
        }

        // Navigate and clear location state so assistant stack is cleared (same outcome as chatKey='new')
        navigate('/ai-assistant', { replace: true, state: {} });
    }, [navigate, dispatch, sessionId]);

    useEffect(() => {
        setNav(<Sessions newSession={handleNewSession} />);
    }, [setNav, handleNewSession]);

    return <Chat key={chatKey} sessionId={sessionId} initialStack={initialStack} />;
}
export default Chatbot;
