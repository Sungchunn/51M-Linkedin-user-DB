'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/AppShell';
import { getApiBaseUrl } from '@/lib/config';
import { addHistoryEntry } from '@/lib/searchHistory';
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

async function fetchWithTimeout(url, timeout = 30000, retries = 1) {
    for (;;) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(url, { signal: controller.signal });
            clearTimeout(id);
            return response;
        } catch (error) {
            clearTimeout(id);
            if (retries > 0) {
                retries -= 1;
                continue;
            }
            if (error.name === 'AbortError') {
                throw new Error('Request timed out - API may be processing large dataset');
            }
            throw error;
        }
    }
}

const ICONS = {
    search: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
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
    atSign: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94" />
        </svg>
    ),
};

/** Searchable multi-select rendered as a chip cloud: selected accent chips
    followed by "+ option" quick-add chips (capped; the search box narrows). */
const MAX_SUGGESTED_OPTIONS = 8;

function MultiSelectFilter({ label, items, status, selected, onToggle, search, onSearch, placeholder }) {
    const suggestions = items.filter((item) => !selected.has(item)).slice(0, MAX_SUGGESTED_OPTIONS);
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
            {status === 'loading' ? (
                <p className={styles.optionHint}>Loading…</p>
            ) : status === 'error' ? (
                <p className={styles.optionError}>Failed to load — is the API running?</p>
            ) : (
                <div className={styles.chipCloud}>
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
                    {suggestions.map((item) => (
                        <button
                            type="button"
                            key={item}
                            className={styles.addChip}
                            onClick={() => onToggle(item)}
                        >
                            + {item}
                        </button>
                    ))}
                    {suggestions.length === 0 && selected.size === 0 && (
                        <p className={styles.optionHint}>No matches</p>
                    )}
                </div>
            )}
        </section>
    );
}

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
    const [contactOpen, setContactOpen] = useState(false);
    const [suggestionsHidden, setSuggestionsHidden] = useState(false);
    const contactRef = useRef(null);

    // Close the contact popover on outside click or Escape
    useEffect(() => {
        if (!contactOpen) return undefined;
        const onDown = (e) => {
            if (contactRef.current && !contactRef.current.contains(e.target)) setContactOpen(false);
        };
        const onKey = (e) => {
            if (e.key === 'Escape') setContactOpen(false);
        };
        document.addEventListener('mousedown', onDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [contactOpen]);

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
        try {
            setSuggestionsHidden(localStorage.getItem(HIDE_SUGGESTIONS_KEY) === 'true');
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

    const allContactsSelected = contacts.size === CONTACT_FILTERS.length;

    // Contact requirements have their own selector + badge, so they don't count here
    const activeFilterCount =
        selectedStates.size +
        selectedIndustries.size +
        [jobTitle, company, skills, minExperience, maxExperience].filter((v) => v.trim() !== '').length;

    // Central submit path: every search (form, suggestion card) goes through
    // here so history + navigation stay consistent.
    const runSearch = async (params) => {
        setSearching(true);
        try {
            const fullParams = { ...params, offset: 0, limit: 200 }; // public-tier API cap is 200
            await addHistoryEntry(params);
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

    // Clears the filter panel only; keyword and contact requirements survive
    // (contacts have their own selector with its own Clear).
    const clearFilters = () => {
        setJobTitle('');
        setCompany('');
        setMinExperience('');
        setMaxExperience('');
        setSkills('');
        setSelectedStates(new Set());
        setSelectedIndustries(new Set());
        setStatesSearch('');
        setIndustrySearch('');
    };

    const resetForm = () => {
        setKeyword('');
        setContacts(new Set());
        clearFilters();
    };

    const handleNewSearch = () => {
        resetForm();
        setFiltersOpen(false);
        setContactOpen(false);
        searchInputRef.current?.focus();
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
        <AppShell mainClassName={styles.homeMain} onNewSearch={handleNewSearch}>
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
                                    <span
                                        className={`${styles.toolbarChevron} ${filtersOpen ? styles.toolbarChevronOpen : ''}`}
                                        aria-hidden="true"
                                    >
                                        {ICONS.chevronDown}
                                    </span>
                                </button>

                                <div className={styles.contactWrap} ref={contactRef}>
                                    <button
                                        type="button"
                                        className={`${styles.toolbarBtn} ${contactOpen || contacts.size > 0 ? styles.toolbarBtnActive : ''}`}
                                        onClick={() => setContactOpen((open) => !open)}
                                        aria-expanded={contactOpen}
                                        aria-haspopup="true"
                                    >
                                        {ICONS.atSign}
                                        <span>Contact</span>
                                        {contacts.size > 0 && (
                                            <span className={styles.filterBadge}>{contacts.size}</span>
                                        )}
                                    </button>
                                    {contactOpen && (
                                        <div className={styles.contactPopover} role="group" aria-label="Required contact info">
                                            <div className={styles.popoverHeader}>
                                                <span className={styles.popoverTitle}>Contact info</span>
                                                {contacts.size > 0 && (
                                                    <button
                                                        type="button"
                                                        className={styles.popoverClear}
                                                        onClick={() => setContacts(new Set())}
                                                    >
                                                        Clear
                                                    </button>
                                                )}
                                            </div>
                                            <p className={styles.popoverHint}>Only include profiles that have:</p>
                                            <button
                                                type="button"
                                                className={`${styles.popoverItem} ${styles.popoverItemAll}`}
                                                aria-pressed={allContactsSelected}
                                                onClick={() => setContacts(
                                                    allContactsSelected
                                                        ? new Set()
                                                        : new Set(CONTACT_FILTERS.map(([key]) => key))
                                                )}
                                            >
                                                <span
                                                    className={`${styles.popoverCheck} ${allContactsSelected || contacts.size > 0 ? styles.popoverCheckActive : ''}`}
                                                    aria-hidden="true"
                                                >
                                                    {allContactsSelected ? '✓' : contacts.size > 0 ? '–' : ''}
                                                </span>
                                                <span>Select all</span>
                                            </button>
                                            <div className={styles.popoverDivider} aria-hidden="true" />
                                            {CONTACT_FILTERS.map(([key, label]) => {
                                                const active = contacts.has(key);
                                                return (
                                                    <button
                                                        type="button"
                                                        key={key}
                                                        className={styles.popoverItem}
                                                        aria-pressed={active}
                                                        onClick={() => toggleIn(setContacts)(key)}
                                                    >
                                                        <span
                                                            className={`${styles.popoverCheck} ${active ? styles.popoverCheckActive : ''}`}
                                                            aria-hidden="true"
                                                        >
                                                            {active ? '✓' : ''}
                                                        </span>
                                                        <span>{label}</span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div className={styles.toolbarRight}>
                                <span className={styles.modeChip}>Hybrid search</span>
                                <button
                                    type="submit"
                                    className={styles.submitBtn}
                                    disabled={searching}
                                    aria-label="Search profiles"
                                >
                                    {searching ? <span className={styles.spinnerRing} aria-hidden="true" /> : ICONS.arrow}
                                </button>
                            </div>
                        </div>
                    </div>

                    <div
                        className={`${styles.filtersCollapse} ${filtersOpen ? styles.filtersCollapseOpen : ''}`}
                        aria-hidden={!filtersOpen}
                    >
                        <div className={styles.filtersCollapseInner}>
                        <div className={styles.filtersPanel}>
                            <div className={styles.filtersHeader}>
                                <span className={styles.filtersTitle}>
                                    Filters
                                    {activeFilterCount > 0 && (
                                        <span className={styles.filterBadge}>{activeFilterCount}</span>
                                    )}
                                </span>
                                <button type="button" className={styles.clearFiltersBtn} onClick={clearFilters}>
                                    Clear all
                                </button>
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

                            </div>

                            <div className={styles.filtersFooter}>
                                <button type="submit" className={styles.applyBtn} disabled={searching}>
                                    Apply filters
                                </button>
                            </div>
                        </div>
                        </div>
                    </div>
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
        </AppShell>
    );
}
