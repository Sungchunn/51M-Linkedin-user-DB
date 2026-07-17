'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GitHubStars from '@/components/GitHubStars';
import SideRays from '@/components/SideRays';
import ThemeToggle from '@/components/ThemeToggle';
import { logout } from '@/lib/auth';
import { getApiBaseUrl } from '@/lib/config';
import { addHistoryEntry, clearHistory, getHistory, removeHistoryEntry } from '@/lib/searchHistory';
import styles from './home.module.css';

const ROTATING_TEXTS = [
    'verified LinkedIn profiles',
    'tech professionals',
    'sales leaders',
    'marketing executives',
    'product managers',
    'software engineers',
];

const SUGGESTION_CHIPS = [
    'Software engineers',
    'Sales leaders',
    'Growth marketers',
    'Data scientists',
    'Founders',
];

const SUGGESTION_CARDS = [
    {
        title: 'Find senior software engineers',
        subtitle: 'Python · 8+ years experience',
        params: { keyword: 'senior software engineer', skills: 'Python', min_experience: '8' },
    },
    {
        title: 'Build a fintech sales pipeline',
        subtitle: 'Sales leaders with verified emails',
        params: { keyword: 'sales director fintech', has_email: true },
    },
    {
        title: 'Scout product leadership',
        subtitle: 'Product managers at big tech',
        params: { keyword: 'product manager', company: 'Google' },
    },
];

const CONTACT_FILTERS = [
    ['has_linkedin', 'LinkedIn'],
    ['has_email', 'Email'],
    ['has_phone', 'Phone'],
    ['has_website', 'Website'],
    ['has_twitter', 'Twitter'],
    ['has_github', 'GitHub'],
];

const HIDE_SUGGESTIONS_KEY = 'hideHomeSuggestions';
const SIDEBAR_COLLAPSED_KEY = 'sidebarCollapsed';

async function fetchWithTimeout(url, timeout = 30000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(id);
        return response;
    } catch (error) {
        clearTimeout(id);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out - API may be processing large dataset');
        }
        throw error;
    }
}

function relativeTime(ts) {
    const diff = Date.now() - ts;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(ts).toLocaleDateString();
}

/** Compact searchable multi-select: search box, removable chips, option list. */
function MultiSelectFilter({ label, items, status, selected, onToggle, search, onSearch, placeholder }) {
    return (
        <section className={styles.filterSection}>
            <h3 className={styles.sectionLabel}>
                {label}
                {selected.size > 0 && <span className={styles.sectionCount}>{selected.size}</span>}
            </h3>
            <div className={styles.optionSearchWrap}>
                {ICONS.search}
                <input
                    type="text"
                    className={styles.optionSearch}
                    placeholder={placeholder}
                    value={search}
                    onChange={(e) => onSearch(e.target.value)}
                />
            </div>
            {selected.size > 0 && (
                <div className={styles.selectedChips}>
                    {Array.from(selected).map((value) => (
                        <button
                            type="button"
                            key={value}
                            className={styles.selectedChip}
                            onClick={() => onToggle(value)}
                            aria-label={`Remove ${value}`}
                        >
                            <span>{value}</span>
                            <span className={styles.chipX} aria-hidden="true">×</span>
                        </button>
                    ))}
                </div>
            )}
            <div className={styles.optionList}>
                {status === 'loading' ? (
                    <p className={styles.optionHint}>Loading…</p>
                ) : status === 'error' ? (
                    <p className={styles.optionError}>Failed to load — is the API running?</p>
                ) : items.length === 0 ? (
                    <p className={styles.optionHint}>No matches</p>
                ) : (
                    items.map((item) => {
                        const active = selected.has(item);
                        return (
                            <button
                                type="button"
                                key={item}
                                className={`${styles.optionItem} ${active ? styles.optionItemActive : ''}`}
                                onClick={() => onToggle(item)}
                                aria-pressed={active}
                            >
                                <span className={styles.optionCheck} aria-hidden="true">{active ? '✓' : ''}</span>
                                <span className={styles.optionText}>{item}</span>
                            </button>
                        );
                    })
                )}
            </div>
        </section>
    );
}

const ICONS = {
    search: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
        </svg>
    ),
    plus: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14" />
        </svg>
    ),
    sliders: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" />
            <line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" />
            <line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" />
            <line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" />
        </svg>
    ),
    arrow: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
    ),
    chevronUp: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m18 15-6-6-6 6" />
        </svg>
    ),
    chevronDown: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m6 9 6 6 6-6" />
        </svg>
    ),
    menu: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
        </svg>
    ),
    panelLeft: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="9" y1="3" x2="9" y2="21" />
        </svg>
    ),
};

export default function SearchPage() {
    const router = useRouter();
    const searchInputRef = useRef(null);

    // Rotating hero text
    const [textIndex, setTextIndex] = useState(0);
    const [textVisible, setTextVisible] = useState(true);

    // Filter option lists
    const [allStates, setAllStates] = useState([]);
    const [allIndustries, setAllIndustries] = useState([]);
    const [statesStatus, setStatesStatus] = useState('loading');
    const [industriesStatus, setIndustriesStatus] = useState('loading');
    const [statesSearch, setStatesSearch] = useState('');
    const [industrySearch, setIndustrySearch] = useState('');
    const [selectedStates, setSelectedStates] = useState(() => new Set());
    const [selectedIndustries, setSelectedIndustries] = useState(() => new Set());

    // Text/number inputs
    const [keyword, setKeyword] = useState('');
    const [jobTitle, setJobTitle] = useState('');
    const [company, setCompany] = useState('');
    const [minExperience, setMinExperience] = useState('');
    const [maxExperience, setMaxExperience] = useState('');
    const [skills, setSkills] = useState('');
    const [contacts, setContacts] = useState(() => new Set());

    // UI state
    const [searching, setSearching] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false); // mobile slide-over
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false); // desktop
    const [suggestionsHidden, setSuggestionsHidden] = useState(false);

    // Search history (localStorage-backed for now; backend/DB persistence later)
    const [history, setHistory] = useState([]);
    const [historyQuery, setHistoryQuery] = useState('');

    // Ray colors come from the --rays-* theme tokens so both modes are covered;
    // re-read on themechange (dispatched by the layout.js theme bootstrap).
    const [rays, setRays] = useState(null);

    useEffect(() => {
        const readRayTokens = () => {
            const tokens = getComputedStyle(document.documentElement);
            setRays({
                color1: tokens.getPropertyValue('--rays-color-1').trim(),
                color2: tokens.getPropertyValue('--rays-color-2').trim(),
                opacity: parseFloat(tokens.getPropertyValue('--rays-opacity')) || 1,
            });
        };
        readRayTokens();
        window.addEventListener('themechange', readRayTokens);
        return () => window.removeEventListener('themechange', readRayTokens);
    }, []);

    useEffect(() => {
        const interval = setInterval(() => {
            setTextVisible(false);
            setTimeout(() => {
                setTextIndex((i) => (i + 1) % ROTATING_TEXTS.length);
                setTextVisible(true);
            }, 300);
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        setHistory(getHistory());
        try {
            setSuggestionsHidden(localStorage.getItem(HIDE_SUGGESTIONS_KEY) === 'true');
            setSidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true');
        } catch (e) { /* localStorage unavailable */ }
    }, []);

    useEffect(() => {
        const apiBase = getApiBaseUrl();
        let cancelled = false;

        const regionsUrl = `${apiBase}/regions?country=${encodeURIComponent('united states')}`;
        fetchWithTimeout(regionsUrl, 30000)
            .then(async (res) => {
                if (!res.ok) {
                    const text = await res.text().catch(() => '');
                    throw new Error(`States fetch failed (${res.status}): ${text}`);
                }
                const data = await res.json();
                if (cancelled) return;
                setAllStates(data.regions.map((r) => r.region));
                setStatesStatus('ready');
            })
            .catch((error) => {
                console.error('Failed to load states:', error);
                if (!cancelled) setStatesStatus('error');
            });

        fetchWithTimeout(`${apiBase}/industries`, 30000)
            .then(async (res) => {
                if (!res.ok) {
                    const text = await res.text().catch(() => '');
                    throw new Error(`Industries fetch failed (${res.status}): ${text}`);
                }
                const data = await res.json();
                if (cancelled) return;
                setAllIndustries(data.industries);
                setIndustriesStatus('ready');
            })
            .catch((error) => {
                console.error('Failed to load industries:', error);
                if (!cancelled) setIndustriesStatus('error');
            });

        return () => {
            cancelled = true;
        };
    }, []);

    const toggleIn = (setFn) => (value) => {
        setFn((prev) => {
            const next = new Set(prev);
            if (next.has(value)) {
                next.delete(value);
            } else {
                next.add(value);
            }
            return next;
        });
    };

    const filteredStates = allStates.filter((s) => s.toLowerCase().includes(statesSearch.toLowerCase()));
    const filteredIndustries = allIndustries.filter((i) => i.toLowerCase().includes(industrySearch.toLowerCase()));

    const filteredHistory = useMemo(() => {
        const q = historyQuery.trim().toLowerCase();
        if (!q) return history;
        return history.filter((entry) => entry.label.toLowerCase().includes(q));
    }, [history, historyQuery]);

    const activeFilterCount =
        selectedStates.size +
        selectedIndustries.size +
        contacts.size +
        [jobTitle, company, skills, minExperience, maxExperience].filter((v) => v.trim() !== '').length;

    // Central submit path: every search (form, suggestion card, history rerun)
    // goes through here so history + navigation stay consistent.
    const runSearch = (params) => {
        setSearching(true);
        try {
            const fullParams = { ...params, offset: 0, limit: 100 }; // API max is 100
            addHistoryEntry(params);
            setHistory(getHistory());
            sessionStorage.setItem('searchParams', JSON.stringify(fullParams));
            router.push('/results');
        } catch (error) {
            console.error('Search submission error:', error);
            setSearching(false);
            alert('Error: ' + error.message);
        }
    };

    const buildParamsFromForm = () => {
        const params = {};
        if (keyword.trim()) params.keyword = keyword.trim();
        if (jobTitle.trim()) params.job_title = jobTitle.trim();
        if (company.trim()) params.company = company.trim();
        if (minExperience.trim()) params.min_experience = minExperience.trim();
        if (maxExperience.trim()) params.max_experience = maxExperience.trim();
        if (skills.trim()) params.skills = skills.trim();

        if (selectedIndustries.size > 0) params.industries = Array.from(selectedIndustries);
        if (selectedStates.size > 0) params.states = Array.from(selectedStates);

        for (const [key] of CONTACT_FILTERS) {
            if (contacts.has(key)) params[key] = true;
        }
        return params;
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        runSearch(buildParamsFromForm());
    };

    const resetForm = () => {
        setKeyword('');
        setJobTitle('');
        setCompany('');
        setMinExperience('');
        setMaxExperience('');
        setSkills('');
        setSelectedStates(new Set());
        setSelectedIndustries(new Set());
        setContacts(new Set());
        setStatesSearch('');
        setIndustrySearch('');
    };

    const handleNewSearch = () => {
        resetForm();
        setFiltersOpen(false);
        setSidebarOpen(false);
        searchInputRef.current?.focus();
    };

    const handleHistoryRerun = (entry) => {
        setSidebarOpen(false);
        runSearch(entry.params);
    };

    const handleHistoryDelete = (id) => {
        removeHistoryEntry(id);
        setHistory(getHistory());
    };

    const handleHistoryClear = () => {
        clearHistory();
        setHistory([]);
    };

    // One toggle for both breakpoints: mobile drives the slide-over,
    // desktop drives the collapsed state (persisted).
    const toggleSidebar = () => {
        if (window.matchMedia('(max-width: 900px)').matches) {
            setSidebarOpen((open) => !open);
            return;
        }
        setSidebarCollapsed((collapsed) => {
            const next = !collapsed;
            try {
                localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
            } catch (e) { /* localStorage unavailable */ }
            return next;
        });
    };

    const handleChipClick = (chip) => {
        setKeyword(chip);
        searchInputRef.current?.focus();
    };

    const toggleSuggestions = () => {
        setSuggestionsHidden((hidden) => {
            const next = !hidden;
            try {
                localStorage.setItem(HIDE_SUGGESTIONS_KEY, String(next));
            } catch (e) { /* localStorage unavailable */ }
            return next;
        });
    };

    return (
        <div className={styles.shell}>
            {rays && (
                <div className={styles.raysBackground} aria-hidden="true">
                    <SideRays
                        speed={2.5}
                        rayColor1={rays.color1}
                        rayColor2={rays.color2}
                        intensity={2}
                        spread={2}
                        origin="top-right"
                        tilt={0}
                        saturation={1.5}
                        blend={0.75}
                        falloff={1.6}
                        opacity={rays.opacity}
                    />
                </div>
            )}

            <button
                type="button"
                className={`${styles.menuBtn} ${sidebarCollapsed ? styles.menuBtnVisible : ''} ${sidebarOpen ? styles.menuBtnHidden : ''}`}
                aria-label="Show sidebar"
                onClick={toggleSidebar}
            >
                {ICONS.menu}
            </button>
            {sidebarOpen && <div className={styles.backdrop} onClick={() => setSidebarOpen(false)} />}

            {/* Sidebar: brand, new search, search history */}
            <aside
                className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : ''} ${sidebarCollapsed ? styles.sidebarCollapsed : ''}`}
            >
                <div className={styles.sidebarTop}>
                    <div className={styles.brandRow}>
                        <Link href="/" className={styles.brand}>PROSPECTIQ</Link>
                        <button
                            type="button"
                            className={styles.collapseBtn}
                            aria-label="Hide sidebar"
                            onClick={toggleSidebar}
                        >
                            {ICONS.panelLeft}
                        </button>
                    </div>
                    <p className={styles.brandSub}>Intelligence-Driven Prospecting</p>

                    <button type="button" className={styles.newSearchBtn} onClick={handleNewSearch}>
                        {ICONS.plus}
                        <span>New Search</span>
                    </button>

                    <div className={styles.historySearchWrapper}>
                        {ICONS.search}
                        <input
                            type="text"
                            className={styles.historySearchInput}
                            placeholder="Search history..."
                            value={historyQuery}
                            onChange={(e) => setHistoryQuery(e.target.value)}
                        />
                    </div>
                </div>

                <div className={styles.historySection}>
                    <div className={styles.historyHeader}>
                        <span>Recent</span>
                        {history.length > 0 && (
                            <button type="button" className={styles.historyClear} onClick={handleHistoryClear}>
                                Clear all
                            </button>
                        )}
                    </div>

                    {filteredHistory.length === 0 ? (
                        <p className={styles.historyEmpty}>
                            {history.length === 0
                                ? 'Your searches will appear here.'
                                : 'No searches match your filter.'}
                        </p>
                    ) : (
                        <ul className={styles.historyList}>
                            {filteredHistory.map((entry) => (
                                <li className={styles.historyRow} key={entry.id}>
                                    <button
                                        type="button"
                                        className={styles.historyItem}
                                        onClick={() => handleHistoryRerun(entry)}
                                        title={entry.label}
                                    >
                                        <span className={styles.historyLabel}>{entry.label}</span>
                                        <span className={styles.historyTime}>{relativeTime(entry.ts)}</span>
                                    </button>
                                    <button
                                        type="button"
                                        className={styles.historyDelete}
                                        aria-label={`Delete "${entry.label}" from history`}
                                        onClick={() => handleHistoryDelete(entry.id)}
                                    >
                                        ×
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                <div className={styles.sidebarBottom}>
                    <nav className={styles.sidebarNav}>
                        <Link href="/dashboard">API Keys</Link>
                        <Link href="/api-docs">API Docs</Link>
                        <a
                            href="/login"
                            onClick={(e) => {
                                e.preventDefault();
                                logout();
                            }}
                        >
                            Logout
                        </a>
                    </nav>
                    <div className={styles.sidebarMeta}>
                        <GitHubStars variant="inline" />
                        <ThemeToggle />
                    </div>
                </div>
            </aside>

            {/* Main pane: hero + search box + suggestions */}
            <main className={styles.main}>
                <div className={styles.contentColumn}>
                    <div className="hero-title">
                        <div className="hero-badge">PROSPECTIQ</div>
                        <h1>
                            Search 497K+{' '}
                            <span
                                id="rotatingText"
                                style={{ transition: 'opacity 0.3s ease-in-out', opacity: textVisible ? 1 : 0 }}
                            >
                                {ROTATING_TEXTS[textIndex]}
                            </span>
                        </h1>
                        <p>GTM intelligence for professionals who live in data</p>
                    </div>

                    <form className={styles.searchForm} onSubmit={handleSubmit}>
                        <div className={styles.searchBox}>
                            <input
                                ref={searchInputRef}
                                type="text"
                                id="keyword"
                                className={styles.searchInput}
                                placeholder="Search talent — role, company, skills..."
                                value={keyword}
                                onChange={(e) => setKeyword(e.target.value)}
                                autoComplete="off"
                            />
                            <div className={styles.searchToolbar}>
                                <div className={styles.toolbarLeft}>
                                    <button
                                        type="button"
                                        className={`${styles.toolbarBtn} ${filtersOpen ? styles.toolbarBtnActive : ''}`}
                                        onClick={() => setFiltersOpen((open) => !open)}
                                        aria-expanded={filtersOpen}
                                    >
                                        {ICONS.sliders}
                                        <span>Filters</span>
                                        {activeFilterCount > 0 && (
                                            <span className={styles.filterBadge}>{activeFilterCount}</span>
                                        )}
                                    </button>
                                </div>
                                <div className={styles.toolbarRight}>
                                    <span className={styles.modeChip}>Hybrid search</span>
                                    <button
                                        type="submit"
                                        className={styles.submitBtn}
                                        disabled={searching}
                                        aria-label="Search profiles"
                                    >
                                        {searching ? <span className="loading">…</span> : ICONS.arrow}
                                    </button>
                                </div>
                            </div>
                        </div>

                        {filtersOpen && (
                            <div className={styles.filtersPanel}>
                                <div className={styles.filtersHeader}>
                                    <span className={styles.filtersTitle}>
                                        Filters
                                        {activeFilterCount > 0 && (
                                            <span className={styles.filterBadge}>{activeFilterCount}</span>
                                        )}
                                    </span>
                                    <div className={styles.filtersHeaderActions}>
                                        <button type="button" className={styles.clearFiltersBtn} onClick={resetForm}>
                                            Clear all
                                        </button>
                                        <button
                                            type="button"
                                            className={styles.filtersClose}
                                            aria-label="Close filters"
                                            onClick={() => setFiltersOpen(false)}
                                        >
                                            ×
                                        </button>
                                    </div>
                                </div>

                                <div className={styles.filtersGrid}>
                                    <section className={styles.filterSection}>
                                        <h3 className={styles.sectionLabel}>Role &amp; company</h3>
                                        <input
                                            type="text"
                                            id="job_title"
                                            className={styles.textInput}
                                            placeholder="Job title — e.g. Software Engineer"
                                            value={jobTitle}
                                            onChange={(e) => setJobTitle(e.target.value)}
                                        />
                                        <input
                                            type="text"
                                            id="company"
                                            className={styles.textInput}
                                            placeholder="Company — e.g. Google"
                                            value={company}
                                            onChange={(e) => setCompany(e.target.value)}
                                        />
                                    </section>

                                    <section className={styles.filterSection}>
                                        <h3 className={styles.sectionLabel}>Experience &amp; skills</h3>
                                        <div className={styles.rangeRow}>
                                            <input
                                                type="number"
                                                id="min_experience"
                                                min="0"
                                                max="80"
                                                className={styles.numberInput}
                                                placeholder="Min yrs"
                                                value={minExperience}
                                                onChange={(e) => setMinExperience(e.target.value)}
                                            />
                                            <span className={styles.rangeDash} aria-hidden="true">–</span>
                                            <input
                                                type="number"
                                                id="max_experience"
                                                min="0"
                                                max="80"
                                                className={styles.numberInput}
                                                placeholder="Max yrs"
                                                value={maxExperience}
                                                onChange={(e) => setMaxExperience(e.target.value)}
                                            />
                                        </div>
                                        <input
                                            type="text"
                                            id="skills"
                                            className={styles.textInput}
                                            placeholder="Skills — Python, React (matches all)"
                                            value={skills}
                                            onChange={(e) => setSkills(e.target.value)}
                                        />
                                    </section>

                                    <MultiSelectFilter
                                        label="US states"
                                        items={filteredStates}
                                        status={statesStatus}
                                        selected={selectedStates}
                                        onToggle={toggleIn(setSelectedStates)}
                                        search={statesSearch}
                                        onSearch={setStatesSearch}
                                        placeholder="Search states..."
                                    />

                                    <MultiSelectFilter
                                        label="Industries"
                                        items={filteredIndustries}
                                        status={industriesStatus}
                                        selected={selectedIndustries}
                                        onToggle={toggleIn(setSelectedIndustries)}
                                        search={industrySearch}
                                        onSearch={setIndustrySearch}
                                        placeholder="Search industries..."
                                    />

                                    <section className={`${styles.filterSection} ${styles.filterSectionWide}`}>
                                        <h3 className={styles.sectionLabel}>Has contact info</h3>
                                        <div className={styles.togglePillRow}>
                                            {CONTACT_FILTERS.map(([key, label]) => {
                                                const active = contacts.has(key);
                                                return (
                                                    <button
                                                        type="button"
                                                        key={key}
                                                        className={`${styles.togglePill} ${active ? styles.togglePillActive : ''}`}
                                                        aria-pressed={active}
                                                        onClick={() => toggleIn(setContacts)(key)}
                                                    >
                                                        {active && <span aria-hidden="true">✓ </span>}
                                                        {label}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </section>
                                </div>
                            </div>
                        )}
                    </form>

                    {/* Suggestions */}
                    <div className={styles.suggestions}>
                        {!suggestionsHidden && (
                            <>
                                <div className={styles.chipRow}>
                                    {SUGGESTION_CHIPS.map((chip) => (
                                        <button
                                            type="button"
                                            className={styles.chip}
                                            key={chip}
                                            onClick={() => handleChipClick(chip)}
                                        >
                                            {ICONS.search}
                                            <span>{chip}</span>
                                        </button>
                                    ))}
                                </div>

                                {SUGGESTION_CARDS.map((card) => (
                                    <button
                                        type="button"
                                        className={styles.suggestionCard}
                                        key={card.title}
                                        onClick={() => runSearch(card.params)}
                                    >
                                        <span className={styles.suggestionTitle}>{card.title}</span>
                                        <span className={styles.suggestionSub}>{card.subtitle}</span>
                                    </button>
                                ))}
                            </>
                        )}

                        <button type="button" className={styles.suggestionsToggle} onClick={toggleSuggestions}>
                            <span>{suggestionsHidden ? 'Show suggestions' : 'Hide suggestions'}</span>
                            {suggestionsHidden ? ICONS.chevronDown : ICONS.chevronUp}
                        </button>
                    </div>

                    <p className={styles.statLine}>497K+ profiles indexed · 50 US states · 12 industries</p>
                </div>
            </main>
        </div>
    );
}
