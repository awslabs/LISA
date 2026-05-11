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

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { v4 as uuidv4 } from 'uuid';
import { LisaChatSession } from '@/components/types';
import { baseConfig, IChatConfiguration } from '@/shared/model/chat.configurations.model';
import { RagConfig } from '../components/RagOptions';
import { IModel } from '@/shared/model/model-management.model';
import { useAppDispatch } from '@/config/store';
import { setBreadcrumbs } from '@/shared/reducers/breadcrumbs.reducer';
import { useAssignSessionProjectMutation } from '@/shared/reducers/session.reducer';
import { useNotificationService } from '@/shared/util/hooks';

export const useSession = (sessionId: string, getSessionById: any) => {
    const dispatch = useAppDispatch();
    const notificationService = useNotificationService(dispatch);
    const auth = useAuth();
    const [assignSessionProject] = useAssignSessionProjectMutation();

    const [session, setSession] = useState<LisaChatSession>(() => ({
        history: [],
        sessionId: '',
        userId: '',
        startTime: new Date(Date.now()).toISOString(),
    }));
    const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
    // Start in loading state when the URL already has a sessionId at mount,
    // since the initial async load is scheduled in the same render via
    // pendingLoad's lazy initializer below.
    const [loadingSession, setLoadingSession] = useState<boolean>(() => Boolean(sessionId));
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);
    const [selectedModel, setSelectedModel] = useState<IModel>();
    const [ragConfig, setRagConfig] = useState<RagConfig>({} as RagConfig);
    const [chatAssistantId, setChatAssistantId] = useState<string | null>(null);
    const [pendingProjectId, setPendingProjectId] = useState<string | null>(null);

    /**
     * SessionId from URL captured at mount via lazy state initializer.
     * Used so we only clear assistant on full-page refresh (not when
     * opening a session from the sidebar).
     */
    const [initialUrlSessionId] = useState<string | null | undefined>(() => sessionId);

    const createNewSession = useCallback(() => {
        const newSessionId = uuidv4();

        // Reset all session-related state
        setChatConfiguration(baseConfig);
        setSelectedModel(undefined);
        setRagConfig({} as RagConfig);
        setChatAssistantId(null);
        setInternalSessionId(newSessionId);
        setPendingProjectId(null);

        const newSession = {
            history: [],
            sessionId: newSessionId,
            userId: auth.user?.profile.sub,
            startTime: new Date(Date.now()).toISOString(),
        };
        setSession(newSession);
        setLoadingSession(false);
    }, [auth.user?.profile.sub]);

    // URL-driven session sync — split into render-phase state seeding and
    // an effect that only performs the async side effects. The render-phase
    // block uses the "store previous render's value" pattern, guarded by a
    // `hasInitialized` flag so the first render also performs setup.
    const [hasInitialized, setHasInitialized] = useState<boolean>(false);
    const [prevSessionId, setPrevSessionId] = useState<string | undefined>(sessionId);
    const [pendingLoad, setPendingLoad] = useState<{ id: string; restoreAssistant: boolean } | null>(null);

    if (!hasInitialized || sessionId !== prevSessionId) {
        if (!hasInitialized) setHasInitialized(true);
        if (sessionId !== prevSessionId) setPrevSessionId(sessionId);
        if (sessionId) {
            if (internalSessionId !== sessionId) {
                setInternalSessionId(sessionId);
                setSession((prev) => ({ ...prev, history: [] }));
                setLoadingSession(true);
                // `restoreAssistant=false` only when the page was reloaded AND
                // the sessionId in the URL is the one captured at mount (i.e.
                // a hard refresh of a chat URL clears assistant selection).
                const nav = performance.getEntriesByType?.('navigation')?.[0] as { type?: string } | undefined;
                const isReload = nav?.type === 'reload';
                const isInitialLoadWithThisSession = initialUrlSessionId === sessionId;
                const restoreAssistant = !(isReload && isInitialLoadWithThisSession);
                setPendingLoad({ id: sessionId, restoreAssistant });
            }
        } else if (!internalSessionId || internalSessionId !== session.sessionId || session.history.length > 0) {
            // No sessionId in URL or transitioning away — create a fresh
            // session (clears assistant selection).
            createNewSession();
        }
    }

    useEffect(() => {
        // Hide breadcrumbs whenever the chat surface is shown / sessionId changes.
        dispatch(setBreadcrumbs([]));
    }, [sessionId, dispatch]);

    useEffect(() => {
        if (!pendingLoad) return;
        // Inline async body so the await boundary is visible to the
        // react-hooks/set-state-in-effect rule (all setState calls below
        // run after the awaited query). A `cancelled` flag prevents
        // stale writes if pendingLoad changes mid-flight.
        let cancelled = false;
        (async () => {
            try {
                const resp = await getSessionById(pendingLoad.id);
                if (cancelled) return;
                let sess: LisaChatSession = resp.data;
                if (sess.history === undefined) {
                    sess = {
                        history: [],
                        sessionId: pendingLoad.id,
                        userId: auth.user?.profile.sub,
                        startTime: new Date(Date.now()).toISOString(),
                    };
                }
                setSession(sess);
                setChatConfiguration(sess.configuration ?? baseConfig);
                setSelectedModel(sess.configuration?.selectedModel ?? undefined);
                setRagConfig(sess.configuration?.ragConfig ?? {} as RagConfig);
                if (pendingLoad.restoreAssistant) {
                    setChatAssistantId((sess.configuration as { chatAssistantId?: string })?.chatAssistantId ?? null);
                } else {
                    setChatAssistantId(null);
                }
            } catch (error) {
                console.error('Error loading session:', error);
            } finally {
                if (!cancelled) setLoadingSession(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [pendingLoad, getSessionById, auth.user]);

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
        pendingProjectId,
        assignSessionProject,
        notificationService,
        setPendingProjectId,
    };
};
