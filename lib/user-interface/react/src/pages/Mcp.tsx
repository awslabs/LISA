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

import { ReactElement, useEffect } from 'react';
import { Route, Routes } from 'react-router-dom';
import McpServerManagementComponent from '@/components/mcp/McpServerManagementComponent';
import { McpServerForm } from '@/components/mcp/McpServerForm';
import McpServerDetails from '@/components/mcp/McpServerDetails';

export function McpServers ({ setNav }): ReactElement {
    useEffect(() => {
        setNav(null);
    }, [setNav]);

    return (
        <Routes>
            <Route index path='*' element={<McpServerManagementComponent />} />
            <Route index path='/new' element={<McpServerForm />} />
            <Route index path='/edit/:mcpServerId' element={<McpServerForm isEdit={true} />} />
            <Route index path='/:mcpServerId' element={<McpServerDetails />} />
        </Routes>
    );
}

export default McpServers;
