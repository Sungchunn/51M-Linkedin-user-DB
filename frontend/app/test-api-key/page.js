'use client';

import { useEffect, useState } from 'react';
import ThemeToggle from '@/components/ThemeToggle';
import { getApiBaseUrl } from '@/lib/config';
import styles from './test-api-key.module.css';

export default function TestApiKeyPage() {
    const [username, setUsername] = useState('admin');
    const [password, setPassword] = useState('admin123');
    const [keyName, setKeyName] = useState('Test Key');

    const [loginResult, setLoginResult] = useState(null);
    const [createResult, setCreateResult] = useState(null);
    const [listResult, setListResult] = useState(null);

    // Auto-load token on page load
    useEffect(() => {
        if (localStorage.getItem('access_token')) {
            setLoginResult({ ok: true, message: '✅ Token found in localStorage' });
        }
    }, []);

    const getToken = () => localStorage.getItem('access_token');

    const testLogin = async () => {
        setLoginResult({ pending: true, message: 'Testing login...' });

        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();

            if (response.ok) {
                localStorage.setItem('access_token', data.access_token);
                setLoginResult({ ok: true, message: '✅ Login successful!', data });
            } else {
                setLoginResult({ ok: false, message: '❌ Login failed', data });
            }
        } catch (error) {
            setLoginResult({ ok: false, message: `❌ Error: ${error.message}` });
        }
    };

    const testCreateKey = async () => {
        const accessToken = getToken();
        if (!accessToken) {
            alert('Please login first!');
            return;
        }

        setCreateResult({ pending: true, message: 'Creating API key...' });

        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/api-keys`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    key_name: keyName,
                    scopes: ['search:read', 'export:read'],
                    tier: 'basic',
                }),
            });

            const data = await response.json();

            if (response.ok) {
                setCreateResult({ ok: true, message: '✅ API Key created!', data, apiKey: data.api_key });
            } else {
                setCreateResult({ ok: false, message: '❌ Failed to create API key', data });
            }
        } catch (error) {
            setCreateResult({ ok: false, message: `❌ Error: ${error.message}` });
        }
    };

    const testListKeys = async () => {
        const accessToken = getToken();
        if (!accessToken) {
            alert('Please login first!');
            return;
        }

        setListResult({ pending: true, message: 'Loading API keys...' });

        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/api-keys`, {
                headers: { Authorization: `Bearer ${accessToken}` },
            });

            const data = await response.json();

            if (response.ok) {
                setListResult({ ok: true, message: `✅ Found ${data.length} API key(s)`, data });
            } else {
                setListResult({ ok: false, message: '❌ Failed to list API keys', data });
            }
        } catch (error) {
            setListResult({ ok: false, message: `❌ Error: ${error.message}` });
        }
    };

    const renderResult = (result) => {
        if (!result) return null;
        return (
            <div>
                <p className={result.pending ? '' : result.ok ? styles.success : styles.error}>{result.message}</p>
                {result.data && <pre>{JSON.stringify(result.data, null, 2)}</pre>}
                {result.apiKey && (
                    <>
                        <p style={{ color: 'var(--error)' }}>⚠️ Save this key! It won&apos;t be shown again:</p>
                        <p className={styles.keyValue}>{result.apiKey}</p>
                    </>
                )}
            </div>
        );
    };

    return (
        <div className={styles.page}>
            <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 100 }}>
                <ThemeToggle />
            </div>
            <h1>API Key Creation Test</h1>

            <div className={styles.section}>
                <h2>Step 1: Login</h2>
                <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} /><br /><br />
                <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} /><br /><br />
                <button onClick={testLogin}>Login</button>
                {renderResult(loginResult)}
            </div>

            <div className={styles.section}>
                <h2>Step 2: Create API Key</h2>
                <input type="text" placeholder="Key Name" value={keyName} onChange={(e) => setKeyName(e.target.value)} /><br /><br />
                <button onClick={testCreateKey}>Create API Key</button>
                {renderResult(createResult)}
            </div>

            <div className={styles.section}>
                <h2>Step 3: List API Keys</h2>
                <button onClick={testListKeys}>List API Keys</button>
                {renderResult(listResult)}
            </div>
        </div>
    );
}
