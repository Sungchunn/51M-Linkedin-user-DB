/**
 * Frontend Configuration
 * Automatically detects environment and sets API base URL
 */

// Detect environment and set API base URL
const getApiBaseUrl = () => {
    // Check if running in production (non-localhost domain)
    const hostname = window.location.hostname;

    // If hostname is localhost or 127.0.0.1, use local development API
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }

    // For production, check if there's a specific API URL in meta tag
    const metaApiUrl = document.querySelector('meta[name="api-url"]');
    if (metaApiUrl && metaApiUrl.content) {
        return metaApiUrl.content;
    }

    // Default: Use same origin (assumes API is served from same domain)
    return window.location.origin;
};

// Export configuration
const API_BASE_URL = getApiBaseUrl();

// Log environment for debugging
console.log('🔧 Environment:', window.location.hostname === 'localhost' ? 'Development' : 'Production');
console.log('🌐 API Base URL:', API_BASE_URL);

// Export for use in other scripts
window.APP_CONFIG = {
    API_BASE_URL: API_BASE_URL,
    VERSION: '1.2.0',
    ENVIRONMENT: window.location.hostname === 'localhost' ? 'development' : 'production'
};
