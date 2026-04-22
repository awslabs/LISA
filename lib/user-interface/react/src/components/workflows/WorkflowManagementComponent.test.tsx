import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import WorkflowManagementComponent from './WorkflowManagementComponent';
import { lisaAxios } from '@/shared/reducers/reducer.utils';

const mockDispatch = vi.fn();
const mockUseAppSelector = vi.fn();

vi.mock('@/config/store', () => ({
    useAppDispatch: () => mockDispatch,
    useAppSelector: (selector: any) => mockUseAppSelector(selector)
}));

vi.mock('@/shared/reducers/reducer.utils', () => ({
    lisaAxios: {
        post: vi.fn()
    }
}));

describe('WorkflowManagementComponent', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        mockDispatch.mockClear();
        mockUseAppSelector.mockReset();
    });

    const mockState = {
        workflow: {
            templates: [{
                id: 'nightly-rag-summary',
                name: 'Nightly RAG Summary',
                description: 'Nightly run'
            }],
            workflows: []
        }
    };

    it('dispatches create-from-template action from UI flow', async () => {
        const user = userEvent.setup();
        mockUseAppSelector.mockImplementation((selector: any) => selector(mockState));
        vi.mocked(lisaAxios.post).mockResolvedValue({
            data: {
                workflowId: 'workflow-service-001',
                name: 'Nightly Smoke (Server)',
                created: '2026-04-22T00:00:00.000Z'
            }
        });

        render(<WorkflowManagementComponent />);
        await user.type(screen.getByTestId('workflow-name-input').querySelector('input')!, 'Nightly Smoke');
        await user.click(screen.getByTestId('workflow-create-from-template'));

        expect(lisaAxios.post).toHaveBeenCalledWith('/workflows', {
            name: 'Nightly Smoke',
            templateId: 'nightly-rag-summary'
        });
        expect(mockDispatch).toHaveBeenCalledWith(expect.objectContaining({
            payload: {
                id: 'workflow-service-001',
                name: 'Nightly Smoke (Server)',
                templateId: 'nightly-rag-summary',
                createdAt: '2026-04-22T00:00:00.000Z'
            }
        }));
    });

    it('does not dispatch and shows error when create request fails', async () => {
        const user = userEvent.setup();
        mockUseAppSelector.mockImplementation((selector: any) => selector(mockState));
        vi.mocked(lisaAxios.post).mockRejectedValue(new Error('failed'));

        render(<WorkflowManagementComponent />);
        await user.type(screen.getByTestId('workflow-name-input').querySelector('input')!, 'Nightly Smoke');
        await user.click(screen.getByTestId('workflow-create-from-template'));

        expect(mockDispatch).not.toHaveBeenCalled();
        expect(await screen.findByTestId('workflow-create-error')).toHaveTextContent('Failed to create workflow');
    });
});
