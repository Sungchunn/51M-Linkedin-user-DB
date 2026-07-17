/**
 * Search history — localStorage-backed (client-side only).
 *
 * NEGATIVE SPACE CONTRACT:
 * - Every entry is { id: string, label: string, params: object, ts: number }
 * - getHistory() always returns an array (never throws), newest first
 * - History is capped at MAX_ENTRIES; addHistoryEntry trims the tail
 * - Re-running an identical search moves it to the top instead of duplicating
 *
 * Backend/DB persistence is planned (per-user history via the API). Keep this
 * module the single access point so the swap to API calls happens in one place.
 */

const STORAGE_KEY = 'searchHistory';
const MAX_ENTRIES = 50;

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

/** Newest-first list of saved searches. Always returns an array. */
export function getHistory() {
    return readStore();
}

/** Save a search. Identical params replace the old entry (moved to top). Returns the new entry. */
export function addHistoryEntry(params) {
    const signature = JSON.stringify(params);
    const entry = {
        id: generateId(),
        label: describeParams(params),
        params,
        ts: Date.now(),
    };
    const rest = readStore().filter((e) => JSON.stringify(e.params) !== signature);
    const next = [entry, ...rest];
    writeStore(next);
    return entry;
}

export function removeHistoryEntry(id) {
    writeStore(readStore().filter((e) => e.id !== id));
}

export function clearHistory() {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        // best-effort
    }
}
