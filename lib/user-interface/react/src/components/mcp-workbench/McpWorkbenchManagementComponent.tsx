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

import { Button, CodeEditor, Grid, SpaceBetween, List, ButtonDropdown } from '@cloudscape-design/components';
import 'react';
import 'ace-builds/css/ace.css';
import 'ace-builds/css/theme/cloud_editor.css';
import 'ace-builds/css/theme/cloud_editor_dark.css';
import * as ace from 'ace-builds';
import 'ace-builds/src-noconflict/mode-python';
import { useState } from 'react';

export function McpWorkbenchManagementComponent () {
    const [files, setFiles] = useState([]);
    // const [loading, setLoading] = useState(true);
    // const [ace, setAce] = useState<any>();

    // useEffect(() => {
    //     aceLoader()
    //         .then(ace => {
    //             setAce(ace);
    //         })
    //         .finally(() => {
    //             setLoading(false);
    //         });
    // }, []);

    return (
        <Grid gridDefinition={[{ colspan: 3 }, { colspan: 9 }]}>
            <SpaceBetween size='s' direction='vertical'>
                <List
                 
                    renderItem={(item: any) => {
                        return {
                            id: item.id,
                            content: item.filename,
                            actions: (<ButtonDropdown
                                items={[
                                    { id: '1', text: 'Action one' },
                                    { id: '2', text: 'Action two' },
                                    { id: '3', text: 'Action three' }
                                ]}
                                variant='icon'
                                ariaLabel={`Actions for ${item.content}`}
                            />)
                        };
                    }}
                    items={files}>
                </List>
                <Button onClick={() => setFiles([...files, {id: files.length + 1, filename: 'my_test.py'}])}>
                    Add File
                </Button>
            </SpaceBetween>
            <CodeEditor
                language='python'
                value='const pi = 3.14;'
                ace={ace}
                // preferences={preferences}
                onDelayedChange={({detail}) => {
                    console.log(detail.value);
                }}
                onPreferencesChange={() => {}}
            // loading={loading}
            // themes={{
            //     light: ["cloud_editor"],
            //     dark: ["cloud_editor_dark"]
            // }}
            />
        </Grid >
    );
}

export default McpWorkbenchManagementComponent;