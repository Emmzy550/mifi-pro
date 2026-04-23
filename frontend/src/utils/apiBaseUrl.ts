const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1']);

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const normalizeRelativeBaseUrl = (value: string) => {
    const normalized = trimTrailingSlash(value);
    if (!normalized) return '/api';
    return normalized.startsWith('/') ? normalized : `/${normalized.replace(/^\/+/, '')}`;
};

export const resolveApiBaseUrl = () => {
    const configuredBaseUrl = import.meta.env.VITE_API_URL?.trim() || '';

    if (typeof window !== 'undefined' && LOCAL_HOSTS.has(window.location.hostname)) {
        if (!configuredBaseUrl || configuredBaseUrl === '/api') {
            return 'http://localhost:8000';
        }
    }

    if (configuredBaseUrl) {
        if (/^https?:\/\//i.test(configuredBaseUrl)) {
            return trimTrailingSlash(configuredBaseUrl);
        }
        return normalizeRelativeBaseUrl(configuredBaseUrl);
    }

    if (typeof window !== 'undefined') {
        return '/api';
    }

    return 'http://localhost:8000';
};

export const buildApiUrl = (path: string) => {
    const baseUrl = resolveApiBaseUrl();
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;

    if (/^https?:\/\//i.test(baseUrl)) {
        return `${baseUrl}${normalizedPath}`;
    }

    if (typeof window !== 'undefined') {
        return `${window.location.origin}${baseUrl}${normalizedPath}`;
    }

    return `${baseUrl}${normalizedPath}`;
};
