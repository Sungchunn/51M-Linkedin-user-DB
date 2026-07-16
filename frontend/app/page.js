'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Footer from '@/components/Footer';
import Header from '@/components/Header';
import SquaresBackground from '@/components/SquaresBackground';
import { getApiBaseUrl } from '@/lib/config';

const ROTATING_TEXTS = [
    'verified LinkedIn profiles',
    'tech professionals',
    'sales leaders',
    'marketing executives',
    'product managers',
    'software engineers',
];

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

function FilterCheckboxList({ idPrefix, items, status, selected, onToggle, errorLabel }) {
    if (status === 'loading') {
        return (
            <div className="industry-tags-container">
                <p style={{ color: 'var(--text-muted)', padding: 8 }}>Loading {errorLabel}...</p>
            </div>
        );
    }

    if (status === 'error') {
        return (
            <div className="industry-tags-container">
                <p style={{ color: 'var(--error)', padding: 8 }}>Error loading {errorLabel}</p>
            </div>
        );
    }

    return (
        <div className="industry-tags-container">
            {items.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', padding: 8 }}>No items found</p>
            ) : (
                items.map((item) => {
                    const inputId = `${idPrefix}_${item.replace(/\s+/g, '_')}`;
                    return (
                        <div className="industry-checkbox" key={item}>
                            <input
                                type="checkbox"
                                id={inputId}
                                value={item}
                                checked={selected.has(item)}
                                onChange={() => onToggle(item)}
                            />
                            <label htmlFor={inputId}>{item}</label>
                        </div>
                    );
                })
            )}
        </div>
    );
}

const SEARCH_ICON = (
    <svg className="filter-search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
    </svg>
);

const CONTACT_FILTERS = [
    ['has_linkedin', 'Has LinkedIn Profile'],
    ['has_email', 'Has Email'],
    ['has_phone', 'Has Phone'],
    ['has_website', 'Has Website/Domain'],
    ['has_twitter', 'Has Twitter'],
    ['has_github', 'Has GitHub'],
];

export default function SearchPage() {
    const router = useRouter();

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

    const [searching, setSearching] = useState(false);

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

    const handleSubmit = (e) => {
        e.preventDefault();
        setSearching(true);

        try {
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

            params.offset = 0;
            params.limit = 100; // API max is 100

            sessionStorage.setItem('searchParams', JSON.stringify(params));
            router.push('/results');
        } catch (error) {
            console.error('Form submission error:', error);
            setSearching(false);
            alert('Error: ' + error.message);
        }
    };

    return (
        <>
            <SquaresBackground />
            <Header />

            {/* Hero Section */}
            <div className="hero-section">
                <div className="hero-background"></div>
                <div className="search-card">
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

                    <form onSubmit={handleSubmit}>
                        {/* Main Search Input */}
                        <div className="search-input-wrapper">
                            <svg className="search-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="11" cy="11" r="8" />
                                <path d="m21 21-4.35-4.35" />
                            </svg>
                            <input
                                type="text"
                                id="keyword"
                                placeholder="senior software engineer, product manager, data scientist..."
                                className="form-control"
                                value={keyword}
                                onChange={(e) => setKeyword(e.target.value)}
                            />
                        </div>

                        {/* Advanced Filters */}
                        <details className="filters-collapsible">
                            <summary className="filters-toggle">Advanced Filters</summary>
                            <div className="filters-content">
                                {/* US States Filter (Multi-select) */}
                                <div className="form-group">
                                    <div className="filter-label-wrapper">
                                        <label htmlFor="statesSearch">US States</label>
                                        {selectedStates.size > 0 && (
                                            <span className="filter-count">{selectedStates.size} selected</span>
                                        )}
                                    </div>
                                    <div className="search-filter-wrapper">
                                        {SEARCH_ICON}
                                        <input
                                            type="text"
                                            id="statesSearch"
                                            placeholder="Search states..."
                                            className="filter-search-input"
                                            value={statesSearch}
                                            onChange={(e) => setStatesSearch(e.target.value)}
                                        />
                                    </div>
                                    <FilterCheckboxList
                                        idPrefix="statesContainer"
                                        items={filteredStates}
                                        status={statesStatus}
                                        selected={selectedStates}
                                        onToggle={toggleIn(setSelectedStates)}
                                        errorLabel="states"
                                    />
                                    <small>Select one or more US states</small>
                                </div>

                                {/* Industry Filter (Multi-select) */}
                                <div className="form-group">
                                    <div className="filter-label-wrapper">
                                        <label htmlFor="industrySearch">Industries</label>
                                        {selectedIndustries.size > 0 && (
                                            <span className="filter-count">{selectedIndustries.size} selected</span>
                                        )}
                                    </div>
                                    <div className="search-filter-wrapper">
                                        {SEARCH_ICON}
                                        <input
                                            type="text"
                                            id="industrySearch"
                                            placeholder="Search industries..."
                                            className="filter-search-input"
                                            value={industrySearch}
                                            onChange={(e) => setIndustrySearch(e.target.value)}
                                        />
                                    </div>
                                    <FilterCheckboxList
                                        idPrefix="industryContainer"
                                        items={filteredIndustries}
                                        status={industriesStatus}
                                        selected={selectedIndustries}
                                        onToggle={toggleIn(setSelectedIndustries)}
                                        errorLabel="industries"
                                    />
                                    <small>Select one or more industries</small>
                                </div>

                                {/* Job Title Filter */}
                                <div className="form-group">
                                    <label htmlFor="job_title">Job Title</label>
                                    <input
                                        type="text"
                                        id="job_title"
                                        placeholder="e.g. Software Engineer, Product Manager"
                                        className="form-control"
                                        value={jobTitle}
                                        onChange={(e) => setJobTitle(e.target.value)}
                                    />
                                    <small>Search for specific job titles</small>
                                </div>

                                {/* Company Filter */}
                                <div className="form-group">
                                    <label htmlFor="company">Company</label>
                                    <input
                                        type="text"
                                        id="company"
                                        placeholder="e.g. Google, Microsoft, Amazon"
                                        className="form-control"
                                        value={company}
                                        onChange={(e) => setCompany(e.target.value)}
                                    />
                                    <small>Search for specific companies</small>
                                </div>

                                {/* Experience Range */}
                                <div className="filters-row">
                                    <div className="form-group">
                                        <label htmlFor="min_experience">Min Experience (years)</label>
                                        <input
                                            type="number"
                                            id="min_experience"
                                            min="0"
                                            max="80"
                                            placeholder="0"
                                            className="form-control"
                                            value={minExperience}
                                            onChange={(e) => setMinExperience(e.target.value)}
                                        />
                                    </div>

                                    <div className="form-group">
                                        <label htmlFor="max_experience">Max Experience (years)</label>
                                        <input
                                            type="number"
                                            id="max_experience"
                                            min="0"
                                            max="80"
                                            placeholder="80"
                                            className="form-control"
                                            value={maxExperience}
                                            onChange={(e) => setMaxExperience(e.target.value)}
                                        />
                                    </div>
                                </div>

                                {/* Skills Filter */}
                                <div className="form-group">
                                    <label htmlFor="skills">Skills</label>
                                    <input
                                        type="text"
                                        id="skills"
                                        placeholder="e.g. Python, JavaScript, React"
                                        className="form-control"
                                        value={skills}
                                        onChange={(e) => setSkills(e.target.value)}
                                    />
                                    <small>Comma-separated skills (AND logic)</small>
                                </div>

                                {/* Contact Information Filters */}
                                <div className="form-group">
                                    <label style={{ display: 'block', marginBottom: 12, color: 'var(--text-primary)', fontWeight: 500 }}>Contact Information</label>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                                        {CONTACT_FILTERS.map(([key, label]) => (
                                            <label className="checkbox-filter" key={key}>
                                                <input
                                                    type="checkbox"
                                                    id={key}
                                                    checked={contacts.has(key)}
                                                    onChange={() => toggleIn(setContacts)(key)}
                                                />
                                                <span>{label}</span>
                                            </label>
                                        ))}
                                    </div>
                                    <small>Select profiles that have specific contact information</small>
                                </div>
                            </div>
                        </details>

                        {/* Search Button */}
                        <div style={{ textAlign: 'center', marginTop: 32 }}>
                            <button type="submit" className="btn-primary" disabled={searching}>
                                {searching ? (
                                    <span className="loading">Searching...</span>
                                ) : (
                                    <span>Search Profiles</span>
                                )}
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            {/* Stats Section */}
            <div className="stats-section">
                <div className="stats-grid">
                    <div className="stat-card">
                        <div className="stat-value">497K+</div>
                        <div className="stat-label">Profiles indexed</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">50</div>
                        <div className="stat-label">US States covered</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">12</div>
                        <div className="stat-label">Industries tracked</div>
                    </div>
                </div>
            </div>

            <Footer />
        </>
    );
}
