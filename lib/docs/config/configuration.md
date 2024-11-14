# Minimal Configuration

Configurations for LISA are split into 2 configuration files, base and custom. The base configuration contains the
minimal properties required to deploy LISA. The file is located at the root of your project (./config-base.yaml) and
contains the following properties:

```yaml
accountNumber:
region:
restApiConfig:
s3BucketModels:
mountS3DebUrl:
```

<!--@include: ./schema.md -->