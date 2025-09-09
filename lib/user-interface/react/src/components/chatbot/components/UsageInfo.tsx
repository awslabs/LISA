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

import { Badge, SpaceBetween } from '@cloudscape-design/components';
import { UsageInfo as UsageInfoType } from '@/components/types';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCircleDown, faCircleUp } from '@fortawesome/free-regular-svg-icons';
import { faStopwatch } from '@fortawesome/free-solid-svg-icons';


type UsageInfoProps = {
    /** Usage information object containing token counts and response time */
    usage?: UsageInfoType;
    /** Whether to show completion tokens count (default: true) */
    showTokens?: boolean;
    /** Whether to show response time (default: true) */
    showResponseTime?: boolean;
};

/**
 * Component for displaying usage information badges including token counts and response time.
 * Used in chat messages to show model performance metrics.
 */

export default function UsageInfo ({
    usage,
    showTokens = true,
    showResponseTime = true,
}: UsageInfoProps) {
    if (!usage) return null;

    return (
        <SpaceBetween direction='horizontal' size='s'>
            {showTokens && usage.completionTokens && (
                <Badge color='green'>Tokens
                    <FontAwesomeIcon icon={faCircleUp} className='pl-1'/> {usage.promptTokens}
                    <FontAwesomeIcon icon={faCircleDown} className='pl-1'/> {usage.completionTokens}
                </Badge>
            )}
            {showResponseTime && usage.responseTime !== undefined && usage.responseTime !== null && (
                <Badge color='green'>Response
                    <FontAwesomeIcon icon={faStopwatch} className='pl-1'/> {usage.responseTime.toFixed(2)}s
                </Badge>
            )}
        </SpaceBetween>
    );
}
