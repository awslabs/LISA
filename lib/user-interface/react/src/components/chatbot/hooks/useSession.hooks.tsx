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

import { useCallback, useEffect, useState, useRef } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { v4 as uuidv4 } from 'uuid';
import { LisaChatSession } from '@/components/types';
import { baseConfig, IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { RagConfig } from '../components/RagOptions';
import { IModel } from '@/shared/model/model-management.model';
import { useAppDispatch } from '@/config/store';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';

export const useSession = (sessionId: string, getSessionById: any) => {
    const dispatch = useAppDispatch();
    const auth = useAuth();

    const [session, setSession] = useState<LisaChatSession>(() => ({
        history: [],
        sessionId: '',
        userId: '',
        startTime: new Date(Date.now()).toISOString(),
    }));
    const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
    const [loadingSession, setLoadingSession] = useState(false);
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);
    const [selectedModel, setSelectedModel] = useState<IModel>();
    const [ragConfig, setRagConfig] = useState<RagConfig>({} as RagConfig);
    const [chatAssistantId, setChatAssistantId] = useState<string | null>(null);
    const hasCreatedNewSessionRef = useRef(false);
    /** SessionId from URL on first run; used so we only clear assistant on refresh (not when opening a session from sidebar). */
    const initialUrlSessionIdRef = useRef<string | undefined | null>(null);

    // Memoize the session loading function to prevent unnecessary re-renders
    const loadSession = useCallback(async (id: string, restoreAssistant: boolean) => {
        try {
            setLoadingSession(true);
            const resp = await getSessionById(id);
            let sess: LisaChatSession = resp.data;

            if (sess.history === undefined) {
                sess = {
                    history: [],
                    sessionId: id,
                    userId: auth.user?.profile.sub,
                    startTime: new Date(Date.now()).toISOString(),
                };
            }
            setSession(sess);
            setChatConfiguration(sess.configuration ?? baseConfig);
            setSelectedModel(sess.configuration?.selectedModel ?? undefined);
            setRagConfig(sess.configuration?.ragConfig ?? {} as RagConfig);
            if (restoreAssistant) {
                setChatAssistantId((sess.configuration as { chatAssistantId?: string })?.chatAssistantId ?? null);
            } else {
                setChatAssistantId(null);
            }
        } catch (error) {
            console.error('Error loading session:', error);
        } finally {
            setLoadingSession(false);
        }
    }, [getSessionById, auth.user?.profile.sub]);

    const createNewSession = useCallback(() => {
        const newSessionId = uuidv4();

        // Reset all session-related state
        setChatConfiguration(baseConfig);
        setSelectedModel(undefined);
        setRagConfig({} as RagConfig);
        setChatAssistantId(null);
        setInternalSessionId(newSessionId);

        const newSession = {
            history: [],
            sessionId: newSessionId,
            userId: auth.user?.profile.sub,
            startTime: new Date(Date.now()).toISOString(),
        };
        setSession(newSession);
        setLoadingSession(false);
    }, [auth.user?.profile.sub]);

    useEffect(() => {
        // always hide breadcrumbs
        dispatch(setBreadcrumbs([]));

        // Capture sessionId from URL on first run (used to clear assistant only on refresh, not when opening from sidebar)
        if (initialUrlSessionIdRef.current === null) {
            initialUrlSessionIdRef.current = sessionId;
        }

        if (sessionId) {
            // Reset the ref when we have a sessionId
            hasCreatedNewSessionRef.current = false;
            // Only load if this is a different session than what we currently have
            if (internalSessionId !== sessionId) {
                setInternalSessionId(sessionId);
                setSession((prev) => ({ ...prev, history: [] }));
                const nav = performance.getEntriesByType?.('navigation')?.[0] as { type?: string } | undefined;
                const isReload = nav?.type === 'reload';
                const isInitialLoadWithThisSession = initialUrlSessionIdRef.current === sessionId;
                const restoreAssistant = !(isReload && isInitialLoadWithThisSession);
                loadSession(sessionId, restoreAssistant);
            }
        } else if (!internalSessionId || internalSessionId !== session.sessionId || session.history.length > 0) {
            // Create new session when: no sessionId in URL, or transitioning from another session.
            // New session => clear assistant selection.
            createNewSession();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, dispatch, loadSession]);

    return {
        session,
        setSession,
        internalSessionId,
        setInternalSessionId,
        loadingSession,
        chatConfiguration,
        setChatConfiguration,
        selectedModel,
        setSelectedModel,
        ragConfig,
        setRagConfig,
        chatAssistantId,
        setChatAssistantId,
    };
};
