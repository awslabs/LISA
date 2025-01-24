/**
 * Format date to a short date time format
 * @param date EPOCH date string | number
 */
export function formatDate (date: string | number): string {
    const dateObj = new Date(typeof date === 'string' ? Number.parseInt(date) : date);
    return dateObj.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
    });
}

/**
 * Format JSON object to a string
 * @param data
 */
export function formatObject (data: object): string {
    return JSON.stringify(data)
        .replaceAll(',', ', ')
        .replaceAll('{', '')
        .replaceAll('}', '')
        .replaceAll('"', '');
}