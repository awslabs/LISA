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

import { default as Axios, AxiosError, AxiosRequestConfig } from 'axios';
import { getBaseURI } from '../../components/utils';

export const lisaAxios = Axios.create({
    baseURL: getBaseURI(),
});

lisaAxios.interceptors.request.use(
    (config) => {
        const oidcString = sessionStorage.getItem(`oidc.user:${window.env.AUTHORITY}:${window.env.CLIENT_ID}`);
        const token = oidcString ? JSON.parse(oidcString).id_token : '';

        if (config.headers === undefined) {
            config.headers = {};
        }

        if (config.data instanceof FormData && config.data.get('x-amz-security-token')){
            return config;
        } else {
            config.headers['Authorization'] = `Bearer ${token}`;
            return config;
        }
    },
    (error) => {
        return Promise.reject(error).catch(axiosCatch);
    },
);

export const lisaBaseQuery =
  ({ baseUrl } = { baseUrl: '' }) =>
      async ({ url, method, data, params, headers }: AxiosRequestConfig) => {
          try {
              const result = await lisaAxios({
                  url: baseUrl + url,
                  method,
                  data,
                  params,
                  headers,
              });

              return { data: result.data };
          } catch (axiosError) {
              const err = axiosError;

              return {
                  error: {
                      status: err.response?.status,
                      data: err.response?.data || err.message,
                  },
              };
          }
      };

export const axiosCatch = (reason: Error | AxiosError) => {
    if (Axios.isAxiosError(reason)) {
        return Promise.reject({
            name: reason.name,
            message: reason.response?.data,
            code: reason.response?.status,
        });
    }
    throw reason;
};
