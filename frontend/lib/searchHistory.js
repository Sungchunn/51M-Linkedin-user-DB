/**
 * Search history — per-user via the API when logged in, localStorage otherwise.
 *
 * NEGATIVE SPACE CONTRACT:
 * - Every entry is { id: string, label: string, params: object, ts: number }
 *   (the /history endpoints return exactly this shape)
 * - All functions are async and never throw; getHistory() always resolves to an
 *   array, newest first
 * - History is capped at MAX_ENTRIES (server enforces the same cap per user)
 * - Re-running an identical search moves it to the top instead of duplicating
 * - Logged-in users read/write ONLY the API store (no localStorage fallback on
 *   error — mixing stores would make entries appear and vanish between loads);
 *   API failures degrade to a console.warn and an empty result / no-op
 * - Client-side only: call from event handlers or useEffect
 */
import { getApiBaseUrl } from './config';
import { getAuthHeaders, isAuthenticated } from './auth';

const STORAGE_KEY = 'searchHistory';
const MAX_ENTRIES = 50;

function useApiStore() {
    return typeof window !== 'undefined' && isAuthenticated();
}

// ---------- localStorage store (anonymous users) ----------

function generateId() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function readStore() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.filter(
            (e) => e && typeof e.id === 'string' && typeof e.label === 'string' && e.params && typeof e.ts === 'number'
        );
    } catch (e) {
        return [];
    }
}

function writeStore(entries) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
    } catch (e) {
        // localStorage unavailable (private browsing, quota) — history is best-effort
    }
}

// ---------- API store (logged-in users) ----------

async function apiRequest(path, options = {}) {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(),
            ...(options.headers || {}),
        },
    });
    if (!response.ok) {
        throw new Error(`history API ${options.method || 'GET'} ${path} -> ${response.status}`);
    }
    return response.status === 204 ? null : response.json();
}

/** Human-readable one-line summary of a search's params (used as the history label). */
export function describeParams(params) {
    if (params.keyword) return params.keyword;

    const parts = [];
    if (params.job_title) parts.push(params.job_title);
    if (params.company) parts.push(`@ ${params.company}`);
    if (params.skills) parts.push(params.skills);
    if (Array.isArray(params.states) && params.states.length > 0) {
        parts.push(params.states.length === 1 ? params.states[0] : `${params.states.length} states`);
    }
    if (Array.isArray(params.industries) && params.industries.length > 0) {
        parts.push(params.industries.length === 1 ? params.industries[0] : `${params.industries.length} industries`);
    }
    if (params.min_experience || params.max_experience) {
        const min = params.min_experience || '0';
        parts.push(params.max_experience ? `${min}–${params.max_experience} yrs` : `${min}+ yrs`);
    }
    const contacts = ['has_linkedin', 'has_email', 'has_phone', 'has_website', 'has_twitter', 'has_github']
        .filter((k) => params[k]);
    if (contacts.length > 0) parts.push(`${contacts.length} contact filter${contacts.length > 1 ? 's' : ''}`);

    return parts.length > 0 ? parts.join(' · ') : 'All profiles';
}

/** Newest-first list of saved searches. Always resolves to an array. */
export async function getHistory() {
    if (useApiStore()) {
        try {
            return await apiRequest('/history');
        } catch (e) {
            console.warn('searchHistory: API list failed', e);
            return [];
        }
    }
    return readStore();
}

/** Save a search. Identical params replace the old entry (moved to top). Resolves to the entry. */
export async function addHistoryEntry(params) {
    const label = describeParams(params);

    if (useApiStore()) {
        try {
            return await apiRequest('/history', {
                method: 'POST',
                body: JSON.stringify({ label, params }),
            });
        } catch (e) {
            console.warn('searchHistory: API save failed', e);
            return null;
        }
    }

    const signature = JSON.stringify(params);
    const entry = { id: generateId(), label, params, ts: Date.now() };
    const rest = readStore().filter((e) => JSON.stringify(e.params) !== signature);
    writeStore([entry, ...rest]);
    return entry;
}

export async function removeHistoryEntry(id) {
    if (useApiStore()) {
        try {
            await apiRequest(`/history/${id}`, { method: 'DELETE' });
        } catch (e) {
            console.warn('searchHistory: API delete failed', e);
        }
        return;
    }
    writeStore(readStore().filter((e) => e.id !== id));
}

export async function clearHistory() {
    if (useApiStore()) {
        try {
            await apiRequest('/history', { method: 'DELETE' });
        } catch (e) {
            console.warn('searchHistory: API clear failed', e);
        }
        return;
    }
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        // best-effort
    }
}
