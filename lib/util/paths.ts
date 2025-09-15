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

import * as path from 'node:path';

export const ROOT_PATH = path.resolve(path.join(__dirname, '..', '..'));
export const VERSION_PATH = path.join(ROOT_PATH, 'VERSION');

export const LAMBDA_PATH = path.join(ROOT_PATH, 'lambda');
export const COMMON_LAYER_PATH = path.join(ROOT_PATH, 'lib', 'core', 'layers', 'common');
export const FASTAPI_LAYER_PATH = path.join(ROOT_PATH, 'lib', 'core', 'layers', 'fastapi');
export const AUTHORIZER_LAYER_PATH = path.join(ROOT_PATH, 'lib', 'core', 'layers', 'authorizer');
export const SDK_PATH = path.join(ROOT_PATH, 'lisa-sdk');
export const RAG_LAYER_PATH = path.join(ROOT_PATH, 'lib', 'rag', 'layer');

export const REST_API_PATH = path.join(ROOT_PATH, 'lib', 'serve', 'rest-api');
export const ECS_MODEL_PATH = path.join(ROOT_PATH, 'lib', 'serve', 'ecs-model');
export const MCP_WORKBENCH_PATH = path.join(ROOT_PATH, 'lib', 'serve', 'mcp-workbench');
export const BATCH_INGESTION_PATH = path.join(ROOT_PATH, 'lib', 'rag', 'ingestion', 'ingestion-image');

export const WEBAPP_PATH = path.join(ROOT_PATH, 'lib', 'user-interface', 'react');
export const WEBAPP_DIST_PATH = path.join(WEBAPP_PATH, 'dist');

export const VECTOR_STORE_DEPLOYER_PATH = path.join(ROOT_PATH, 'vector_store_deployer');
export const VECTOR_STORE_DEPLOYER_DIST_PATH = path.join(VECTOR_STORE_DEPLOYER_PATH, 'dist');
export const ECS_MODEL_DEPLOYER_PATH = path.join(ROOT_PATH, 'ecs_model_deployer');
export const ECS_MODEL_DEPLOYER_DIST_PATH = path.join(ECS_MODEL_DEPLOYER_PATH, 'dist');

export const DOCS_PATH = path.join(ROOT_PATH, 'lib', 'docs');
export const DOCS_DIST_PATH = path.join(DOCS_PATH, 'dist');

export const SSL_CERT_DIR = '/etc/pki/tls/certs';
export const SSL_CERT_FILE = '/etc/pki/tls/certs/ca-bundle.crt';
