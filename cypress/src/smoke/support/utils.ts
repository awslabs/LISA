import { times, random } from 'lodash';

export const toBase64Url = (obj: { alg: string; typ: string; }) =>
    btoa(JSON.stringify(obj))
        .replace(/=+$/, '')
        .replace(/\+/g, '-')
        .replace(/\//g, '_');

export const randomString = (length: number) =>
    times(length, () => random(36).toString(36)).join('');

export const randomUUID = () =>
    [8, 4, 4, 4, 12]
        .map((len) => times(len, () => random(16).toString(16)).join(''))
        .join('-');
