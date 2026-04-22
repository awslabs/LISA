import { describe, expect, it } from 'vitest';
import workflowReducer, { createWorkflowFromResponse } from './workflow.reducer';

describe('workflow reducer', () => {
    it('creates a workflow from backend response identity payload', () => {
        const state = workflowReducer(undefined, createWorkflowFromResponse({
            id: 'workflow-service-123',
            name: 'Nightly Summary Job (Approved)',
            templateId: 'nightly-rag-summary'
        }));

        expect(state.workflows).toHaveLength(1);
        expect(state.workflows[0].id).toBe('workflow-service-123');
        expect(state.workflows[0].name).toBe('Nightly Summary Job (Approved)');
        expect(state.workflows[0].templateId).toBe('nightly-rag-summary');
        expect(state.workflows[0].templateName).toBe('Nightly RAG Summary');
    });
});
