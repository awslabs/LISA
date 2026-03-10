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

import { useListProjectsQuery } from '@/shared/reducers/project.reducer';
import { IConfiguration } from '@/shared/model/configuration.model';

export const useProjects = (config: IConfiguration | undefined) => {
    const projectsEnabled = config?.configuration?.enabledComponents?.projectOrganization === true;
    const maxProjects = config?.configuration?.maxProjectsPerUser ?? 10; // fallback for pre-migration configs
    const { data: projects = [] } = useListProjectsQuery(undefined, { skip: !projectsEnabled });

    return { projects, projectsEnabled, maxProjects };
};
