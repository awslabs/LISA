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
import { S3UploadRequest } from '../shared/reducers/rag.reducer';

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

export const uploadToS3Request = (presignedUrlResponse: Response, file: File): S3UploadRequest => {
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

    return {
        url: url,
        body: formData
    };
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
