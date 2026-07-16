/** @type {import('next').NextConfig} */
const nextConfig = {
    // Legacy static-site URLs (frontend was plain .html files before Next.js)
    async redirects() {
        return [
            { source: '/index.html', destination: '/', permanent: false },
            { source: '/login.html', destination: '/login', permanent: false },
            { source: '/dashboard.html', destination: '/dashboard', permanent: false },
            { source: '/results.html', destination: '/results', permanent: false },
            { source: '/api-docs.html', destination: '/api-docs', permanent: false },
            { source: '/test-api-key.html', destination: '/test-api-key', permanent: false },
        ];
    },
};

export default nextConfig;
