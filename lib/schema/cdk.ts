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

/**
 * This is a list of exported types from cdk library. Use these when possible to avoid importing the massive aws-cdk-lib dependency
 */

/* eslint-disable @typescript-eslint/no-duplicate-enum-values */
export enum EcsSourceType {
    ASSET = 'asset',
    ECR = 'ecr',
    REGISTRY = 'registry',
    TARBALL = 'tarball',
    EXTERNAL = 'external' // Use provided without modification
}

export enum RemovalPolicy {
    DESTROY = 'destroy',
    RETAIN = 'retain',
    SNAPSHOT = 'snapshot',
    RETAIN_ON_UPDATE_OR_DELETE = 'retain-on-update-or-delete'
}

export enum EbsDeviceVolumeType {
    STANDARD = 'standard',
    IO1 = 'io1',
    IO2 = 'io2',
    GP2 = 'gp2',
    GP3 = 'gp3',
    ST1 = 'st1',
    SC1 = 'sc1',
    GENERAL_PURPOSE_SSD = 'gp2',
    GENERAL_PURPOSE_SSD_GP3 = 'gp3',
    PROVISIONED_IOPS_SSD = 'io1',
    PROVISIONED_IOPS_SSD_IO2 = 'io2',
    THROUGHPUT_OPTIMIZED_HDD = 'st1',
    COLD_HDD = 'sc1',
    MAGNETIC = 'standard'
}

export enum AmiHardwareType {
    STANDARD = 'Standard',
    GPU = 'GPU',
    ARM = 'ARM64',
    NEURON = 'Neuron'
}

/**
 * Load balancing protocol for application load balancers
 */
export enum ApplicationProtocol {
    /**
     * HTTP
     */
    HTTP = 'HTTP',
    /**
     * HTTPS
     */
    HTTPS = 'HTTPS'
}
/**
 * Load balancing protocol version for application load balancers
 */
export enum ApplicationProtocolVersion {
    /**
     * GRPC
     */
    GRPC = 'GRPC',
    /**
     * HTTP1
     */
    HTTP1 = 'HTTP1',
    /**
     * HTTP2
     */
    HTTP2 = 'HTTP2'
}

/* eslint-enable @typescript-eslint/no-duplicate-enum-values */
