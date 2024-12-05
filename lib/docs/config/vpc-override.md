# VPC and Subnet Configuration Overrides

## Overview

This guide will help you configure VPC and subnet overrides for your environment. The configuration allows you to
customize network settings including CIDR blocks, availability zones, and subnet configurations.

## Network Architecture

The configuration supports the following subnet types:

Public Subnets `[ publicSubnet1, publicSubnet2 ]`

Private Subnets `[privateSubnet1, privateSubnet2]`

Private Isolated Subnets `[privateIsolatedSubnet1, privateIsolatedSubnet2 ]`

## Configuration Example

Below is a sample VPC and subnet configuration exported from a running LISA deployment. You can use this as a template
for your overrides:

```json

{
  "Description": "LISA-networking: app-dev",
  "Resources": {
    "Vpc": {
      "Type": "AWS::EC2::VPC",
      "Properties": {
        "CidrBlock": "10.0.0.0/22",
        "EnableDnsHostnames": true,
        "EnableDnsSupport": true
      },
      "publicSubnet1": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2a",
          "CidrBlock": "10.0.0.0/26",
          "MapPublicIpOnLaunch": true
        }
      },
      "publicSubnet2": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2b",
          "CidrBlock": "10.0.0.64/26",
          "MapPublicIpOnLaunch": true,
          "VpcId": {
            "Ref": "VpcVPC8B8C4E4B"
          }
        }
      },
      "VpcVPCprivateIsolatedSubnet1Subnet595DCC9B": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2a",
          "CidrBlock": "10.0.0.128/26",
          "MapPublicIpOnLaunch": false,
          "VpcId": {
            "Ref": "VpcVPC8B8C4E4B"
          }
        }
      },
      "VpcVPCprivateIsolatedSubnet2SubnetFD505B6C": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2b",
          "CidrBlock": "10.0.0.192/26",
          "MapPublicIpOnLaunch": false,
          "VpcId": {
            "Ref": "VpcVPC8B8C4E4B"
          }
        }
      },
      "VpcVPCprivateSubnet1Subnet29B9FADC": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2a",
          "CidrBlock": "10.0.1.0/26",
          "MapPublicIpOnLaunch": false,
          "VpcId": {
            "Ref": "VpcVPC8B8C4E4B"
          }
        }
      },
      "VpcVPCprivateSubnet2Subnet63498DC1": {
        "Type": "AWS::EC2::Subnet",
        "Properties": {
          "AvailabilityZone": "us-west-2b",
          "CidrBlock": "10.0.1.64/26",
          "MapPublicIpOnLaunch": false,
          "VpcId": {
            "Ref": "VpcVPC8B8C4E4B"
          }
        }
      }
    }
  }
}
```

## Required Properties

For each subnet, you must specify:

AvailabilityZone

CidrBlock

VpcId

MapPublicIpOnLaunch (true for public subnets, false for private)

## Best Practices

1. Distribute subnets across different Availability Zones for high availability

2. Ensure CIDR blocks don't overlap between subnets

3. Plan IP address space according to your workload requirements

4. Enable DNS support and hostnames in the VPC

```
VPC (10.0.0.0/22)
├── Public Subnet 1    (10.0.0.0/26)   - AZ a
├── Public Subnet 2    (10.0.0.64/26)  - AZ b
├── Private Subnet 1   (10.0.0.128/26) - AZ a
├── Private Subnet 2   (10.0.0.192/26) - AZ b
├── Isolated Subnet 1  (10.0.1.0/26)   - AZ a
└── Isolated Subnet 2  (10.0.1.64/26)  - AZ b
```