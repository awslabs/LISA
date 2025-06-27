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
import { useAuth } from 'react-oidc-context';
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

    const [session, setSession] = useState<LisaChatSession>({
        history: [],
        sessionId: '',
        userId: '',
        startTime: new Date(Date.now()).toISOString(),
    });
    const [internalSessionId, setInternalSessionId] = useState<string | null>(null);
    const [loadingSession, setLoadingSession] = useState(false);
    const [chatConfiguration, setChatConfiguration] = useState<IChatConfiguration>(baseConfig);
    const [selectedModel, setSelectedModel] = useState<IModel>();
    const [ragConfig, setRagConfig] = useState<RagConfig>({} as RagConfig);

    useEffect(() => {
        // always hide breadcrumbs
        dispatch(setBreadcrumbs([]));

        if (sessionId) {
            setInternalSessionId(sessionId);
            setLoadingSession(true);
            setSession((prev) => ({ ...prev, history: [] }));

            getSessionById(sessionId).then((resp: any) => {
                // session doesn't exist so we create it
                let sess: LisaChatSession = resp.data;
                if (sess.history === undefined) {
                    sess = {
                        history: [],
                        sessionId: sessionId,
                        userId: auth.user?.profile.sub,
                        startTime: new Date(Date.now()).toISOString(),
                    };
                }
                setSession(sess);
                setChatConfiguration(sess.configuration ?? baseConfig);
                setSelectedModel(sess.configuration?.selectedModel ?? undefined);
                setRagConfig(sess.configuration?.ragConfig ?? {} as RagConfig);
                setLoadingSession(false);
            });
        } else {
            const newSessionId = uuidv4();
            setChatConfiguration(baseConfig);
            setInternalSessionId(newSessionId);
            const newSession = {
                history: [],
                sessionId: newSessionId,
                userId: auth.user?.profile.sub,
                startTime: new Date(Date.now()).toISOString(),
            };
            setSession(newSession);
        }
    }, [sessionId, dispatch, auth.user?.profile.sub, getSessionById]);

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
    };
};
