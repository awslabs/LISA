# Minimal Configuration

Configurations for LISA are split into 2 configuration files, base and custom. The base configuration contains the
recommended properties that can be overridden with the custom properties file. The custom configuration should contain 
the minimal properties required to deploy LISA, and any optional properties or overrides. This file should be created 
at the root of your project (./config-custom.yaml) and needs to contain the following properties:

```yaml
accountNumber:
region:
s3BucketModels:
authConfig:
  authority:
  clientId:
  adminGroup:
  jwtGroupsProperty:
```

<!--@include: ./schema.md -->
