/**
 * Frontend configuration — API base URL detection.
 *
 * Resolution order:
 * 1. NEXT_PUBLIC_API_URL env var (replaces the old <meta name="api-url"> tag)
 * 2. localhost / 127.0.0.1 → local development API on :8000
 * 3. same origin (assumes API is served from the same domain)
 */
export function getApiBaseUrl() {
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL;
    }

    if (typeof window === 'undefined') {
        // Server render — pages only fetch client-side, so this is just a safe default.
        return 'http://localhost:8000';
    }

    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }

    return window.location.origin;
}
