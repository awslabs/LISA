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

import React, { ReactElement } from 'react';
import { useAppDispatch } from '@/config/store';
import { modelManagementApi, useGetAllModelsQuery } from '@/shared/reducers/model-management.reducer';
import { RefreshButton } from '@/components/common/RefreshButton';

function ModelLibraryActions (): ReactElement {
    const dispatch = useAppDispatch();
    const { isFetching } = useGetAllModelsQuery();

    return (
        <RefreshButton
            isLoading={isFetching}
            onClick={() => {
                dispatch(modelManagementApi.util.invalidateTags(['models']));
            }}
            ariaLabel='Refresh models cards'
        />
    );
}

export { ModelLibraryActions };
