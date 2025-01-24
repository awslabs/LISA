import { BreadcrumbGroup } from '@cloudscape-design/components';
import { useLocation, useNavigate } from 'react-router-dom';
import React from 'react';

interface BreadcrumbItem {
    text: string;
    href: string;
}

export const Breadcrumbs: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const getBreadcrumbItems = (): BreadcrumbItem[] => {
        const pathSegments = location.pathname.split('/').filter(segment => segment);
        // Create breadcrumb items array, starting with home
        const items: BreadcrumbItem[] = [
            { text: 'Home', href: '/' },
        ];

        let currentPath = '';
        pathSegments.forEach(segment => {
            currentPath += `/${segment}`;
            const text = segment
                .split('-')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');

            items.push({
                text,
                href: currentPath,
            });
        });

        return items;
    };

    return (
        <BreadcrumbGroup
            items={getBreadcrumbItems()}
            ariaLabel="Breadcrumbs"
            onFollow={(event) => {
                // Prevent default behavior
                event.preventDefault();
                navigate(event.detail.href);
            }}
        />
    );
};
