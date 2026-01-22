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

import { ReactElement } from 'react';
import { Button, Icon, Spinner } from '@cloudscape-design/components';

export type RefreshButtonProps = {
    isLoading: boolean;
    onClick: () => void;
    ariaLabel?: string;
};

export function RefreshButton({ isLoading, onClick, ariaLabel = 'Refresh' }: RefreshButtonProps): ReactElement {
    return (
        <Button
            onClick={onClick}
            disabled={isLoading}
            ariaLabel={ariaLabel}
        >
            {isLoading ? <Spinner size="normal" /> : <Icon name="refresh" />}
        </Button>
    );
}

export default RefreshButton;
