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

import {
  LisaChatSession,
  LisaChatMessageFields,
  PutSessionRequestBody,
  LisaChatMessage,
  Repository,
  ModelTypes,
  Model,
} from './types';

const stripTrailingSlash = (str) => {
  return str && str.endsWith('/') ? str.slice(0, -1) : str;
};

export const RESTAPI_URI = stripTrailingSlash(window.env.RESTAPI_URI);
export const RESTAPI_VERSION = window.env.RESTAPI_VERSION;

/**
 * Gets base URI for API Gateway. This can either be the APIGW execution URL directly or a
 * custom domain.
 */
export const getBaseURI = (): string => {
  return window.env.API_BASE_URL;
};

/**
 * Send an authenticated request to the backend. Handles adding the proper authorization header
 * @param url the URL to make a fetch request to
 * @param method the API method (GET, PUT, DELETE, etc)
 * @param idToken the user's ID token from authenticating
 * @param body the body of the request
 * @param headers optionally include additional headers like ContentType
 * @returns
 */
export const sendAuthenticatedRequest = async (
  url: string,
  method: string,
  idToken: string,
  body?: BodyInit,
  headers?: Record<string, string>,
): Promise<Response> => {
  headers = {
    ...headers,
    Authorization: `Bearer ${idToken}`,
  };
  let fetchUrl = url;
  if (!url.includes(RESTAPI_URI)) {
    fetchUrl = `${getBaseURI()}${url}`;
  }
  let resp: Response;
  if (body) {
    resp = await fetch(fetchUrl, {
      method: method,
      mode: 'cors',
      headers: headers,
      body: body,
    });
  } else {
    resp = await fetch(fetchUrl, {
      method: method,
      mode: 'cors',
      headers: headers,
    });
  }
  return resp;
};

/**
 * Creates a session using the history from prior sessions
 * @param session contains information about the current chat session such as sessionId and chat history
 * @param idToken the user's ID token from authenticating
 */
export const putSession = async (session: LisaChatSession, idToken: string): Promise<void> => {
  const body: PutSessionRequestBody = {
    messages: session.history.map((elem) => {
      const message: LisaChatMessageFields = {
        content: elem.content,
        type: elem.type,
        metadata: elem.metadata,
      };
      return message;
    }),
  };

  await sendAuthenticatedRequest(`session/${session.sessionId}`, 'PUT', idToken, JSON.stringify(body));
};

/**
 * Retrieves session information from a prior session, including chat history
 * @param sessionId the session ID of an existing chat session
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const getSession = async (sessionId: string, idToken: string): Promise<LisaChatSession> => {
  const resp = await sendAuthenticatedRequest(`session/${sessionId}`, 'GET', idToken);
  const sess = (await resp.json()) as LisaChatSession;
  if (sess.history != undefined) {
    sess.history = sess.history.map(
      (elem) =>
        new LisaChatMessage({
          type: elem.type,
          content: elem.content,
          metadata: elem.metadata,
        }),
    );
  }
  return sess;
};

/**
 * Lists all sessions associated with this user
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const listSessions = async (idToken: string): Promise<LisaChatSession[]> => {
  const resp = await sendAuthenticatedRequest(`session`, 'GET', idToken);
  const sessArray = (await resp.json()) as LisaChatSession[];
  for (const sess of sessArray) {
    sess.history = sess.history.map(
      (elem) =>
        new LisaChatMessage({
          type: elem.type,
          content: elem.content,
          metadata: elem.metadata,
        }),
    );
  }
  return sessArray;
};

/**
 * Deletes the given session
 * @param sessionId the session ID of an existing chat session
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const deleteSession = async (sessionId: string, idToken: string) => {
  const resp = await sendAuthenticatedRequest(`session/${sessionId}`, 'DELETE', idToken);
  return await resp.json();
};

/**
 * Deletes all sessions associated with this user
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const deleteUserSessions = async (idToken: string) => {
  const resp = await sendAuthenticatedRequest(`session`, 'DELETE', idToken);
  return await resp.json();
};

/**
 * Describes all models of a given type which are available to a user
 * @param modelType model type we are requesting
 * @returns
 */
export const describeModels = (modelType: ModelTypes): Model[] => {
  return window.env.MODELS?.filter((m) => m.modelType === modelType).map((m) => ({
    id: m.model,
    streaming: m.streaming,
    modelType: m.modelType,
  }));
};

/**
 * Returns true or false based on the model health status
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const isModelInterfaceHealthy = async (idToken: string): Promise<boolean> => {
  const resp = await sendAuthenticatedRequest(`${RESTAPI_URI}/health`, 'GET', idToken);
  return resp.ok;
};

/**
 * Created default opensearch rag repository
 * @param idToken the user's ID token from authenticating
 * @returns
 */
export const listRagRepositories = async (idToken: string): Promise<Repository[]> => {
  const resp = await sendAuthenticatedRequest(`repository`, 'GET', idToken);
  return await resp.json();
};

export const getPresignedUrl = async (idToken: string, body: string): Promise<Response> => {
  const resp = await sendAuthenticatedRequest(`repository/presigned-url`, 'POST', idToken, body);
  return resp.json();
};

export const uploadToS3 = async (presignedUrlResponse: Response, file: File): Promise<number> => {
  const presignedUrl = presignedUrlResponse['response'];
  //This method uploads a file to S3 using a pre-signed post
  const url = presignedUrl.url;
  /*
      The S3 PutObject API accepts form data, and an attached binary file.
      Here, we add the form fields returned by the API, build a form
      and attach the file. Finally, we send the request to S3.
  */
  const formData = new FormData();
  for (const key in presignedUrl.fields) {
    formData.append(key, presignedUrl.fields[key]);
  }

  formData.append('file', file); // The binary file must be appended last

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  return response.status;
};

export const ingestDocuments = async (
  idToken: string,
  documents: string[],
  repositoryId: string,
  embeddingModel: Model,
  repostiroyType: string,
  chunkSize: number,
  chunkOverlap: number,
): Promise<number> => {
  const resp = await sendAuthenticatedRequest(
    `repository/${repositoryId}/bulk?repositoryType=${repostiroyType}&chunkSize=${chunkSize}&chunkOverlap=${chunkOverlap}`,
    'POST',
    idToken,
    JSON.stringify({
      embeddingModel: {
        modelName: embeddingModel.id,
      },
      keys: documents,
    }),
  );
  return resp.status;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const formatDocumentsAsString = (docs: any, forMetadata = false): string => {
  let contents = '';
  (docs || []).forEach((doc, index) => {
    if (forMetadata && doc.Document?.metadata?.source) {
      contents += `${index > 0 ? '\n' : ''}Source - ${doc.Document.metadata.source}:`;
    }
    contents += `\n${doc.Document.page_content}\n`;
  });
  return contents;
};
