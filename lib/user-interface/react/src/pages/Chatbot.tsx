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

import { useCallback, useEffect, useState, useRef } from 'react';

import Chat from '../components/chatbot/Chat';
import Sessions from '../components/chatbot/components/Sessions';
import { useAppDispatch } from '@/config/store';
import { sessionApi } from '@/shared/reducers/session.reducer';

export function Chatbot ({ setNav }) {
    const { sessionId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const dispatch = useAppDispatch();
    const [key, setKey] = useState(() => new Date().toISOString());
    const prevSessionIdRef = useRef(sessionId);
    const initialStack = location.state?.stack;

    const handleNewSession = useCallback(() => {
        // Clear specific cached session data that might interfere with new session creation
        if (sessionId) {
            dispatch(sessionApi.util.invalidateTags([{ type: 'session', id: sessionId }]));
        }

        // Always update the key to force Chat component remount and clear state
        // This ensures state is cleared even when already on /ai-assistant (no UUID in URL)
        setKey(new Date().toISOString());

        // Navigate and clear location state so assistant stack is cleared (fixes needing New twice)
        navigate('/ai-assistant', { replace: true, state: {} });
    }, [navigate, dispatch, sessionId]);

    // Update key when sessionId changes from a value to undefined (new session clicked)
    useEffect(() => {
        if (prevSessionIdRef.current && !sessionId) {
            // We transitioned from having a sessionId to not having one (new session)
            queueMicrotask(() => setKey(new Date().toISOString()));
        }
        prevSessionIdRef.current = sessionId;
    }, [sessionId]);

    // Remount Chat when starting from a stack so it applies stack config to new session
    useEffect(() => {
        if (initialStack) {
            setKey(`stack-${initialStack.stackId}`);
        }
    }, [initialStack?.stackId]);

    useEffect(() => {
        setNav(<Sessions newSession={handleNewSession} />);
    }, [setNav, handleNewSession]);

    return <Chat key={key} sessionId={sessionId} initialStack={initialStack} />;
}
export default Chatbot;
