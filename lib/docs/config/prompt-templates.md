# Prompt Templates API

LISA includes prompt template APIs to help teams standardize common prompts and reuse them across chat workflows.

## Overview

Prompt Templates in LISA are reusable prompt artifacts that can be created by users (or administrators), edited over time, and selected in chat workflows. They are primarily used to standardize how teams prompt models and to reduce repeated prompt authoring.

LISA supports two common prompt styles:

- **Directive prompts**: Instruction-focused templates that define what the model should do (for example, summarize, extract entities, classify, or generate structured output).
- **Persona prompts**: Role-focused templates that define how the model should respond (for example, tone, audience, communication style, and level of detail).

These styles can be used independently or combined. A common pattern is to use a persona prompt to establish communication style, then a directive prompt to enforce task-specific behavior and output format.

### Visibility and Access Model

Prompt templates can be scoped to different audiences in LISA:

- **Private**: Visible only to the creator; useful for personal workflows and experimentation.
- **Shared to IDP groups**: Available to specific identity-provider groups; useful for team- or role-specific prompt libraries.
- **Global**: Available to all users; useful for organization-wide standards, approved templates, and common operational workflows.

This model lets organizations balance flexibility and governance: individuals can iterate quickly with private templates, teams can collaborate through group-scoped templates, and administrators can publish vetted global templates for broad reuse.

### Suggested Usage

- Use **directive prompts** for repeatable tasks that require consistent output structure.
- Use **persona prompts** for consistency in voice and audience fit.
- Use **group-shared templates** for domain teams (for example, operations, engineering, or compliance).
- Use **global templates** for officially approved prompts that should be broadly discoverable.

## API Reference

Base path: `/prompt-templates`

### List Prompt Templates

- Method: `GET`
- Path: `/prompt-templates`
- Description: Lists prompt templates available to the caller.

### Create Prompt Template

- Method: `POST`
- Path: `/prompt-templates`
- Description: Creates a new prompt template.

### Get Prompt Template

- Method: `GET`
- Path: `/prompt-templates/{promptTemplateId}`
- Description: Returns a specific prompt template.

Path parameters:

- `promptTemplateId` (string, required): Prompt template identifier

### Update Prompt Template

- Method: `PUT`
- Path: `/prompt-templates/{promptTemplateId}`
- Description: Updates a specific prompt template.

Path parameters:

- `promptTemplateId` (string, required): Prompt template identifier

### Delete Prompt Template

- Method: `DELETE`
- Path: `/prompt-templates/{promptTemplateId}`
- Description: Deletes a specific prompt template.

Path parameters:

- `promptTemplateId` (string, required): Prompt template identifier

Example:

```bash
curl -X GET "https://<api-gateway-domain>/<stage>/prompt-templates" \
  -H "Authorization: Bearer <token>"
```
