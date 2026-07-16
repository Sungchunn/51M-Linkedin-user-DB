'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GitHubStars from '@/components/GitHubStars';
import SquaresBackground from '@/components/SquaresBackground';
import ThemeToggle from '@/components/ThemeToggle';
import { getAuthHeaders, isAuthenticated, logout } from '@/lib/auth';
import { getApiBaseUrl } from '@/lib/config';
import styles from './dashboard.module.css';

const SCOPE_OPTIONS = ['search:read', 'export:read', 'pii:read'];

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
        return `${diffMins} min ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
    return date.toLocaleDateString();
}

export default function DashboardPage() {
    const router = useRouter();

    const [authChecked, setAuthChecked] = useState(false);
    const [username, setUsername] = useState('User');
    const [keys, setKeys] = useState(null); // null while loading
    const [keysError, setKeysError] = useState(false);

    // Create-key modal state
    const [modalOpen, setModalOpen] = useState(false);
    const [keyName, setKeyName] = useState('');
    const [scopes, setScopes] = useState(() => new Set(['search:read']));
    const [tier, setTier] = useState('public');
    const [creating, setCreating] = useState(false);
    const [createdKey, setCreatedKey] = useState(null);
    const [copied, setCopied] = useState(false);

    const loadApiKeys = useCallback(async () => {
        setKeysError(false);
        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/api-keys`, {
                headers: getAuthHeaders(),
            });
            if (!response.ok) {
                throw new Error('Failed to load API keys');
            }
            setKeys(await response.json());
        } catch (error) {
            console.error('Error loading API keys:', error);
            setKeysError(true);
        }
    }, []);

    useEffect(() => {
        if (!isAuthenticated()) {
            router.replace('/login');
            return;
        }
        setAuthChecked(true);

        const loadUserProfile = async () => {
            try {
                const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
                    headers: getAuthHeaders(),
                });
                if (!response.ok) {
                    throw new Error('Failed to load profile');
                }
                const user = await response.json();
                setUsername(user.username);
            } catch (error) {
                console.error('Error loading profile:', error);
                logout();
            }
        };

        loadUserProfile();
        loadApiKeys();
    }, [router, loadApiKeys]);

    const openCreateKeyModal = () => {
        setKeyName('');
        setScopes(new Set(['search:read']));
        setTier('public');
        setCreatedKey(null);
        setCopied(false);
        setModalOpen(true);
    };

    const closeCreateKeyModal = () => setModalOpen(false);

    const toggleScope = (scope) => {
        setScopes((prev) => {
            const next = new Set(prev);
            if (next.has(scope)) {
                next.delete(scope);
            } else {
                next.add(scope);
            }
            return next;
        });
    };

    const handleCreateKey = async (e) => {
        e.preventDefault();

        if (scopes.size === 0) {
            alert('Please select at least one scope');
            return;
        }

        setCreating(true);
        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/api-keys`, {
                method: 'POST',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    key_name: keyName.trim(),
                    scopes: Array.from(scopes),
                    tier,
                }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || error.detail || 'Failed to create API key');
            }

            const newKey = await response.json();
            setCreatedKey(newKey.api_key);
            await loadApiKeys();
        } catch (error) {
            console.error('Error creating API key:', error);
            alert(error.message);
        } finally {
            setCreating(false);
        }
    };

    const copyApiKey = () => {
        navigator.clipboard.writeText(createdKey).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    const revokeApiKey = async (keyId, name) => {
        if (!confirm(`Are you sure you want to revoke "${name}"? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`${getApiBaseUrl()}/auth/api-keys/${keyId}`, {
                method: 'DELETE',
                headers: getAuthHeaders(),
            });
            if (!response.ok) {
                throw new Error('Failed to revoke API key');
            }
            await loadApiKeys();
        } catch (error) {
            console.error('Error revoking API key:', error);
            alert('Failed to revoke API key. Please try again.');
        }
    };

    if (!authChecked) {
        return null;
    }

    return (
        <>
            <SquaresBackground />
            <GitHubStars variant="floating" style={{ position: 'fixed', top: 20, right: 20, zIndex: 100 }} />
            <div className={styles.dashboardContainer}>
                <div className={styles.dashboardHeader}>
                    <div>
                        <div className={styles.dashboardTitle}><Link href="/">PROSPECTIQ</Link></div>
                        <div className={styles.userInfo}>Welcome, <span>{username}</span></div>
                    </div>
                    <div className={styles.userMenu}>
                        <ThemeToggle />
                        <button className={styles.logoutBtn} onClick={logout}>Logout</button>
                    </div>
                </div>

                <div className={styles.dashboardSection}>
                    <div className={styles.sectionHeader}>
                        <div className={styles.sectionTitle}>API Keys</div>
                        <button className={styles.btnPrimary} onClick={openCreateKeyModal}><span>+ Create New Key</span></button>
                    </div>

                    <div className={styles.apiKeysList}>
                        {keysError ? (
                            <div className={styles.emptyState} style={{ color: 'var(--error)' }}>
                                ⚠️ Error loading API keys. Please refresh the page.
                            </div>
                        ) : keys === null ? (
                            <div className={styles.emptyState}>Loading API keys...</div>
                        ) : keys.length === 0 ? (
                            <div className={styles.emptyState}>
                                No API keys yet. Create your first key to get started!
                            </div>
                        ) : (
                            keys.map((key) => (
                                <div className={styles.apiKeyCard} key={key.id}>
                                    <div className={styles.apiKeyInfo}>
                                        <div className={styles.apiKeyName}>{key.key_name}</div>
                                        <div className={styles.apiKeyDetails}>
                                            <span className={styles.apiKeyPrefix}>{key.key_prefix}...</span>
                                            <span>•</span>
                                            <span>Tier: {key.tier}</span>
                                            <span>•</span>
                                            <span>Uses: {key.usage_count}</span>
                                            {key.last_used_at && (
                                                <>
                                                    <span>•</span>
                                                    <span>Last used: {formatDate(key.last_used_at)}</span>
                                                </>
                                            )}
                                        </div>
                                        <div className={styles.apiKeyScopes}>
                                            {key.scopes.map((scope) => (
                                                <span className={styles.scopeBadge} key={scope}>{scope}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className={styles.apiKeyActions}>
                                        <button className={styles.btnRevoke} onClick={() => revokeApiKey(key.id, key.key_name)}>
                                            Revoke
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className={styles.navLinks}>
                    <Link href="/api-docs">API Documentation</Link>
                    <a
                        href="/login"
                        onClick={(e) => {
                            e.preventDefault();
                            localStorage.clear();
                            router.push('/login');
                        }}
                    >
                        Register New User
                    </a>
                </div>
            </div>

            {/* Create API Key Modal */}
            {modalOpen && (
                <div
                    className={styles.modal}
                    onClick={(e) => {
                        if (e.target === e.currentTarget) closeCreateKeyModal();
                    }}
                >
                    <div className={styles.modalContent}>
                        <div className={styles.modalHeader}>Create New API Key</div>

                        <form onSubmit={handleCreateKey}>
                            {!createdKey && (
                                <>
                                    <div className={styles.formGroup}>
                                        <label className={styles.formLabel} htmlFor="keyName">Key Name</label>
                                        <input
                                            type="text"
                                            id="keyName"
                                            className={styles.formInput}
                                            placeholder="My Project Key"
                                            required
                                            value={keyName}
                                            onChange={(e) => setKeyName(e.target.value)}
                                        />
                                    </div>

                                    <div className={styles.formGroup}>
                                        <label className={styles.formLabel}>Scopes</label>
                                        <div className={styles.checkboxGroup}>
                                            {SCOPE_OPTIONS.map((scope) => (
                                                <label className={styles.checkboxLabel} key={scope}>
                                                    <input
                                                        type="checkbox"
                                                        checked={scopes.has(scope)}
                                                        onChange={() => toggleScope(scope)}
                                                    />
                                                    <span>{scope}</span>
                                                </label>
                                            ))}
                                        </div>
                                    </div>

                                    <div className={styles.formGroup}>
                                        <label className={styles.formLabel} htmlFor="tier">Tier</label>
                                        <select
                                            id="tier"
                                            className={styles.formSelect}
                                            value={tier}
                                            onChange={(e) => setTier(e.target.value)}
                                        >
                                            <option value="public">Public (10 requests/min)</option>
                                            <option value="basic">Basic (200 requests/min)</option>
                                            <option value="trusted">Trusted (1000 requests/min)</option>
                                        </select>
                                    </div>
                                </>
                            )}

                            {createdKey && (
                                <div className={styles.apiKeyCreated}>
                                    <div className={styles.apiKeyCreatedTitle}>✓ API Key Created!</div>
                                    <div className={styles.apiKeyValue}>{createdKey}</div>
                                    <button
                                        type="button"
                                        className={`${styles.copyBtn} ${copied ? 'btn-copied' : ''}`}
                                        onClick={copyApiKey}
                                    >
                                        {copied ? 'Copied!' : 'Copy to Clipboard'}
                                    </button>
                                    <p style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>
                                        ⚠️ Save this key now. You won&apos;t be able to see it again!
                                    </p>
                                </div>
                            )}

                            <div className={styles.modalActions}>
                                <button type="button" className={styles.btnCancel} onClick={closeCreateKeyModal}>
                                    {createdKey ? 'Close' : 'Cancel'}
                                </button>
                                {!createdKey && (
                                    <button type="submit" className={styles.btnPrimary} disabled={creating}>
                                        <span>{creating ? 'Creating...' : 'Create Key'}</span>
                                    </button>
                                )}
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    );
}
