'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { getApiBaseUrl } from '@/lib/config';
import { isAuthenticated, logout } from '@/lib/auth';
import ThemeToggle from '@/components/ThemeToggle';
import GitHubStars from '@/components/GitHubStars';
import styles from './api-docs.module.css';

const NAV_SECTIONS = [
    {
        title: 'Getting Started',
        links: [
            ['introduction', 'Introduction'],
            ['authentication', 'Authentication'],
            ['rate-limits', 'Rate Limits'],
            ['quick-start', 'Quick Start'],
            ['curl-generator', '🔧 cURL Generator'],
        ],
    },
    {
        title: 'Endpoints',
        links: [
            ['health', 'Health Check'],
            ['search', 'Search Profiles'],
            ['filters', 'Filter Options'],
            ['export', 'Export Data'],
        ],
    },
    {
        title: 'Resources',
        links: [
            ['pagination', 'Pagination'],
            ['examples', 'Code Examples'],
            ['errors', 'Error Handling'],
        ],
    },
];

// Document order — used by the scroll spy (same offsetTop - 100 logic as the old page).
const SECTION_IDS = [
    'introduction',
    'curl-generator',
    'authentication',
    'rate-limits',
    'quick-start',
    'health',
    'search',
    'filters',
    'export',
    'pagination',
    'examples',
    'errors',
];

const CONTACT_FLAGS = [
    ['has_linkedin', 'Has LinkedIn Profile'],
    ['has_email', 'Has Email'],
    ['has_phone', 'Has Phone'],
    ['has_website', 'Has Website/Domain'],
    ['has_twitter', 'Has Twitter'],
    ['has_github', 'Has GitHub'],
];

function toggleSetValue(set, value) {
    const next = new Set(set);
    if (next.has(value)) {
        next.delete(value);
    } else {
        next.add(value);
    }
    return next;
}

export default function ApiDocsPage() {
    // cURL generator — filter data
    const [allRegions, setAllRegions] = useState([]);
    const [regionsStatus, setRegionsStatus] = useState('loading');
    const [allIndustries, setAllIndustries] = useState([]);
    const [industriesStatus, setIndustriesStatus] = useState('loading');
    const [regionsSearch, setRegionsSearch] = useState('');
    const [industriesSearch, setIndustriesSearch] = useState('');
    const [selectedRegions, setSelectedRegions] = useState(new Set());
    const [selectedIndustries, setSelectedIndustries] = useState(new Set());

    // cURL generator — form inputs
    const [apiKey, setApiKey] = useState('');
    const [query, setQuery] = useState('');
    const [minExp, setMinExp] = useState('');
    const [maxExp, setMaxExp] = useState('');
    const [limit, setLimit] = useState('20');
    const [offset, setOffset] = useState('0');
    const [skills, setSkills] = useState('');
    const [jobTitle, setJobTitle] = useState('');
    const [company, setCompany] = useState('');
    const [contactFlags, setContactFlags] = useState({
        has_linkedin: false,
        has_email: false,
        has_phone: false,
        has_website: false,
        has_twitter: false,
        has_github: false,
    });

    // cURL generator — output
    const [curlCommand, setCurlCommand] = useState('');
    const [copied, setCopied] = useState(false);
    const curlOutputRef = useRef(null);
    const copyTimerRef = useRef(null);

    // Navigation
    const [activeSection, setActiveSection] = useState('');
    const [showBackToTop, setShowBackToTop] = useState(false);

    // Auth gate — equivalent of the old inline redirect.
    useEffect(() => {
        if (!isAuthenticated()) {
            window.location.href = '/login';
        }
    }, []);

    // Load regions and industries for the cURL generator (in parallel).
    useEffect(() => {
        let cancelled = false;
        const apiBase = getApiBaseUrl();

        async function loadRegions() {
            try {
                const response = await fetch(`${apiBase}/regions?country=united+states`);
                if (!response.ok) {
                    throw new Error(`regions request failed: ${response.status}`);
                }
                const data = await response.json();
                if (cancelled) return;
                setAllRegions(data.regions.map((r) => r.region).sort());
                setRegionsStatus('ready');
            } catch (error) {
                console.error('Failed to load curl filters:', error);
                if (!cancelled) setRegionsStatus('error');
            }
        }

        async function loadIndustries() {
            try {
                const response = await fetch(`${apiBase}/industries`);
                if (!response.ok) {
                    throw new Error(`industries request failed: ${response.status}`);
                }
                const data = await response.json();
                if (cancelled) return;
                setAllIndustries(data.industries.sort());
                setIndustriesStatus('ready');
            } catch (error) {
                console.error('Failed to load curl filters:', error);
                if (!cancelled) setIndustriesStatus('error');
            }
        }

        loadRegions();
        loadIndustries();

        return () => {
            cancelled = true;
        };
    }, []);

    // Scroll spy + back-to-top visibility.
    useEffect(() => {
        function onScroll() {
            setShowBackToTop(window.scrollY > 300);

            let current = '';
            SECTION_IDS.forEach((id) => {
                const section = document.getElementById(id);
                if (section && window.scrollY >= section.offsetTop - 100) {
                    current = id;
                }
            });
            setActiveSection(current);
        }

        window.addEventListener('scroll', onScroll);
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    // Scroll the generated command into view once it renders.
    useEffect(() => {
        if (curlCommand && curlOutputRef.current) {
            curlOutputRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [curlCommand]);

    // Clear any pending copy-feedback timer on unmount.
    useEffect(() => {
        return () => clearTimeout(copyTimerRef.current);
    }, []);

    function handleNavClick(event, id) {
        event.preventDefault();
        const target = document.getElementById(id);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
            setActiveSection(id);
        }
    }

    function handleLogout(event) {
        event.preventDefault();
        logout();
    }

    function toggleContactFlag(flag) {
        setContactFlags((prev) => ({ ...prev, [flag]: !prev[flag] }));
    }

    function generateCurl() {
        const baseUrl = getApiBaseUrl();
        const params = new URLSearchParams();

        const trimmedQuery = query.trim();
        if (trimmedQuery) params.set('q', trimmedQuery);
        params.set('limit', limit || '20');
        params.set('offset', offset || '0');
        params.set('location_country', 'united states');

        // Iterate the sorted source lists so param order is deterministic.
        allRegions.filter((r) => selectedRegions.has(r)).forEach((r) => params.append('regions', r));
        allIndustries.filter((i) => selectedIndustries.has(i)).forEach((i) => params.append('industries', i));

        if (minExp) params.set('min_years_experience', minExp);
        if (maxExp) params.set('max_years_experience', maxExp);

        if (skills.trim()) {
            skills.split(',').map((s) => s.trim()).filter(Boolean).forEach((skill) => {
                params.append('skills', skill);
            });
        }

        // Job title and company filters
        if (jobTitle.trim()) params.set('job_title', jobTitle.trim());
        if (company.trim()) params.set('company', company.trim());

        // Contact information filters
        CONTACT_FLAGS.forEach(([flag]) => {
            if (contactFlags[flag]) params.set(flag, 'true');
        });

        const url = `${baseUrl}/search?${params.toString()}`;

        let command = `curl -X GET "${url}"`;
        if (apiKey.trim()) {
            command += ` \\\n  -H "X-API-Key: ${apiKey.trim()}"`;
        }
        command += ` \\\n  -H "Accept: application/json"`;

        setCurlCommand(command);
    }

    function copyCurlCommand() {
        navigator.clipboard.writeText(curlCommand).then(() => {
            setCopied(true);
            clearTimeout(copyTimerRef.current);
            copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
        }).catch((err) => {
            console.error('Failed to copy:', err);
            alert('Failed to copy to clipboard. Please copy manually.');
        });
    }

    const filteredRegions = allRegions.filter(
        (r) => r.toLowerCase().includes(regionsSearch.toLowerCase())
    );
    const filteredIndustries = allIndustries.filter(
        (i) => i.toLowerCase().includes(industriesSearch.toLowerCase())
    );

    function renderCheckboxList(status, items, selected, onToggle, labels) {
        if (status === 'loading') {
            return <p className={styles.listPlaceholder}>{labels.loading}</p>;
        }
        if (status === 'error') {
            return <p className={styles.listError}>{labels.error}</p>;
        }
        if (items.length === 0) {
            return <p className={styles.listPlaceholder}>No items found</p>;
        }
        return items.map((item) => (
            <label key={item} className={styles.checkItem}>
                <input
                    type="checkbox"
                    checked={selected.has(item)}
                    onChange={() => onToggle(item)}
                />
                <span className={styles.checkItemLabel}>{item}</span>
            </label>
        ));
    }

    return (
        <div className={styles.page}>
            <GitHubStars variant="floating" style={{ position: 'fixed', top: 20, right: 32, zIndex: 100 }} />

            {/* Sidebar */}
            <nav className={styles.sidebar}>
                <div className={styles.sidebarHeader}>
                    <div className={styles.sidebarTop}>
                        <div>
                            <div className={styles.sidebarTitle}>
                                <Link href="/" className={styles.sidebarTitleLink}>PROSPECTIQ API</Link>
                            </div>
                            <div className={styles.sidebarSubtitle}>v1.0.0</div>
                        </div>
                        <ThemeToggle />
                    </div>
                    <div className={styles.sidebarLinks}>
                        <Link href="/" className={styles.sidebarQuickLink}>← Search</Link>
                        <Link href="/dashboard" className={styles.sidebarQuickLink}>API Keys</Link>
                        <a href="/login" className={styles.sidebarQuickLink} onClick={handleLogout}>Logout</a>
                    </div>
                </div>

                {NAV_SECTIONS.map((section) => (
                    <div key={section.title} className={styles.navSection}>
                        <div className={styles.navSectionTitle}>{section.title}</div>
                        {section.links.map(([id, label]) => (
                            <a
                                key={id}
                                href={`#${id}`}
                                className={`${styles.navLink}${activeSection === id ? ` ${styles.active}` : ''}`}
                                onClick={(event) => handleNavClick(event, id)}
                            >
                                {label}
                            </a>
                        ))}
                    </div>
                ))}
            </nav>

            {/* Main Content */}
            <main className={styles.mainContent}>
                {/* Header */}
                <div className={styles.pageHeader}>
                    <h1 className={styles.pageTitle}>API Documentation</h1>
                    <p className={styles.pageDescription}>
                        Complete reference for the PROSPECTIQ API. Search 497K+ LinkedIn profiles with semantic search,
                        advanced filtering, and bulk export capabilities.
                    </p>
                </div>

                {/* Quick Links */}
                <div className={styles.quickLinks}>
                    <a href="#quick-start" className={styles.quickLinkCard} onClick={(event) => handleNavClick(event, 'quick-start')}>
                        <div className={styles.quickLinkTitle}>Quick Start</div>
                        <div className={styles.quickLinkDescription}>Get up and running in 5 minutes</div>
                    </a>
                    <a href="#search" className={styles.quickLinkCard} onClick={(event) => handleNavClick(event, 'search')}>
                        <div className={styles.quickLinkTitle}>Search Endpoint</div>
                        <div className={styles.quickLinkDescription}>Semantic search with filters</div>
                    </a>
                    <a href="#examples" className={styles.quickLinkCard} onClick={(event) => handleNavClick(event, 'examples')}>
                        <div className={styles.quickLinkTitle}>Code Examples</div>
                        <div className={styles.quickLinkDescription}>cURL, JavaScript, Python</div>
                    </a>
                    <Link href="/dashboard" className={styles.quickLinkCard}>
                        <div className={styles.quickLinkTitle}>Get API Key</div>
                        <div className={styles.quickLinkDescription}>Generate your API key</div>
                    </Link>
                </div>

                {/* Introduction */}
                <section id="introduction" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Introduction</h2>
                    <p className={styles.sectionDescription}>
                        The PROSPECTIQ API provides programmatic access to semantic talent search across 497K+ LinkedIn profiles.
                        Our hybrid search combines vector embeddings (80%) with traditional lexical matching (20%) for optimal relevance.
                    </p>

                    <div className={styles.infoBox}>
                        <div className={styles.infoBoxTitle}>Base URL</div>
                        <div className={styles.infoBoxContent}>
                            <code>http://localhost:8000</code>
                        </div>
                    </div>

                    <h3 className={styles.subheading}>Key Features</h3>
                    <ul>
                        <li><strong>Semantic Search:</strong> Natural language queries using OpenAI embeddings</li>
                        <li><strong>Advanced Filters:</strong> Location, skills, experience, industry, and more</li>
                        <li><strong>Bulk Export:</strong> CSV and NDJSON formats for CRM integration</li>
                        <li><strong>Real-time Performance:</strong> Sub-second query responses</li>
                        <li><strong>Flexible Authentication:</strong> API keys with custom scopes and rate limits</li>
                    </ul>
                </section>

                {/* cURL Generator */}
                <section id="curl-generator" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>🔧 cURL Command Generator</h2>
                    <p className={styles.sectionDescription}>
                        Generate ready-to-use cURL commands with live data from the dataset. Select your filters and get a copy-paste ready command.
                    </p>

                    <div className={styles.curlContainer}>
                        {/* API Key Input */}
                        <div className={styles.formGroup}>
                            <label className={styles.fieldLabel} htmlFor="curlApiKey">
                                API Key (optional)
                            </label>
                            <input
                                type="text"
                                id="curlApiKey"
                                placeholder="your-api-key-here"
                                className={`${styles.textInput} ${styles.monoInput}`}
                                value={apiKey}
                                onChange={(event) => setApiKey(event.target.value)}
                            />
                            <small className={styles.hint}>Leave empty for public access (limited features)</small>
                        </div>

                        {/* Search Query */}
                        <div className={styles.formGroup}>
                            <label className={styles.fieldLabel} htmlFor="curlQuery">
                                Search Query
                            </label>
                            <input
                                type="text"
                                id="curlQuery"
                                placeholder="e.g. senior software engineer, product manager, data scientist"
                                className={styles.textInput}
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                            />
                        </div>

                        {/* Filters Row */}
                        <div className={styles.filtersGrid}>
                            {/* Regions Filter */}
                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlRegionsSearch">
                                    US States (multi-select)
                                    <span className={styles.selectedCount}>
                                        {selectedRegions.size > 0 ? `(${selectedRegions.size} selected)` : ''}
                                    </span>
                                </label>
                                <input
                                    type="text"
                                    id="curlRegionsSearch"
                                    placeholder="Search states..."
                                    className={styles.filterSearchInput}
                                    value={regionsSearch}
                                    onChange={(event) => setRegionsSearch(event.target.value)}
                                />
                                <div className={styles.checkboxList}>
                                    {renderCheckboxList(
                                        regionsStatus,
                                        filteredRegions,
                                        selectedRegions,
                                        (item) => setSelectedRegions((prev) => toggleSetValue(prev, item)),
                                        { loading: 'Loading states...', error: 'Failed to load states' }
                                    )}
                                </div>
                            </div>

                            {/* Industries Filter */}
                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlIndustriesSearch">
                                    Industries (multi-select)
                                    <span className={styles.selectedCount}>
                                        {selectedIndustries.size > 0 ? `(${selectedIndustries.size} selected)` : ''}
                                    </span>
                                </label>
                                <input
                                    type="text"
                                    id="curlIndustriesSearch"
                                    placeholder="Search industries..."
                                    className={styles.filterSearchInput}
                                    value={industriesSearch}
                                    onChange={(event) => setIndustriesSearch(event.target.value)}
                                />
                                <div className={styles.checkboxList}>
                                    {renderCheckboxList(
                                        industriesStatus,
                                        filteredIndustries,
                                        selectedIndustries,
                                        (item) => setSelectedIndustries((prev) => toggleSetValue(prev, item)),
                                        { loading: 'Loading industries...', error: 'Failed to load industries' }
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Experience Range */}
                        <div className={styles.rangeGrid}>
                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlMinExp">
                                    Min Experience (years)
                                </label>
                                <input
                                    type="number"
                                    id="curlMinExp"
                                    min="0"
                                    max="80"
                                    placeholder="0"
                                    className={styles.textInput}
                                    value={minExp}
                                    onChange={(event) => setMinExp(event.target.value)}
                                />
                            </div>

                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlMaxExp">
                                    Max Experience (years)
                                </label>
                                <input
                                    type="number"
                                    id="curlMaxExp"
                                    min="0"
                                    max="80"
                                    placeholder="80"
                                    className={styles.textInput}
                                    value={maxExp}
                                    onChange={(event) => setMaxExp(event.target.value)}
                                />
                            </div>

                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlLimit">
                                    Limit
                                </label>
                                <input
                                    type="number"
                                    id="curlLimit"
                                    min="1"
                                    max="1000"
                                    className={styles.textInput}
                                    value={limit}
                                    onChange={(event) => setLimit(event.target.value)}
                                />
                            </div>

                            <div>
                                <label className={styles.fieldLabel} htmlFor="curlOffset">
                                    Offset
                                </label>
                                <input
                                    type="number"
                                    id="curlOffset"
                                    min="0"
                                    className={styles.textInput}
                                    value={offset}
                                    onChange={(event) => setOffset(event.target.value)}
                                />
                            </div>
                        </div>

                        {/* Skills */}
                        <div className={styles.formGroup}>
                            <label className={styles.fieldLabel} htmlFor="curlSkills">
                                Skills (comma-separated)
                            </label>
                            <input
                                type="text"
                                id="curlSkills"
                                placeholder="e.g. Python, JavaScript, React, SQL"
                                className={styles.textInput}
                                value={skills}
                                onChange={(event) => setSkills(event.target.value)}
                            />
                            <small className={styles.hint}>Profiles must have ALL listed skills (AND logic)</small>
                        </div>

                        {/* Job Title Filter */}
                        <div className={styles.formGroup}>
                            <label className={styles.fieldLabel} htmlFor="curlJobTitle">
                                Job Title
                            </label>
                            <input
                                type="text"
                                id="curlJobTitle"
                                placeholder="e.g. Software Engineer, Product Manager"
                                className={styles.textInput}
                                value={jobTitle}
                                onChange={(event) => setJobTitle(event.target.value)}
                            />
                            <small className={styles.hint}>Search for specific job titles (partial match)</small>
                        </div>

                        {/* Company Filter */}
                        <div className={styles.formGroup}>
                            <label className={styles.fieldLabel} htmlFor="curlCompany">
                                Company
                            </label>
                            <input
                                type="text"
                                id="curlCompany"
                                placeholder="e.g. Google, Microsoft, Amazon"
                                className={styles.textInput}
                                value={company}
                                onChange={(event) => setCompany(event.target.value)}
                            />
                            <small className={styles.hint}>Search for specific companies (partial match)</small>
                        </div>

                        {/* Contact Information Filters */}
                        <div className={styles.formGroup}>
                            <span className={`${styles.fieldLabel} ${styles.fieldLabelWide}`}>
                                Contact Information Filters
                            </span>
                            <div className={styles.checkGrid}>
                                {CONTACT_FLAGS.map(([flag, label]) => (
                                    <label key={flag} className={styles.checkRow}>
                                        <input
                                            type="checkbox"
                                            checked={contactFlags[flag]}
                                            onChange={() => toggleContactFlag(flag)}
                                        />
                                        <span className={styles.checkRowLabel}>{label}</span>
                                    </label>
                                ))}
                            </div>
                            <small className={styles.hint}>Filter profiles that have specific contact information</small>
                        </div>

                        {/* Generate Button */}
                        <div className={styles.generateWrap}>
                            <button type="button" className={styles.generateBtn} onClick={generateCurl}>
                                🔧 Generate cURL Command
                            </button>
                        </div>

                        {/* Generated cURL Output */}
                        {curlCommand && (
                            <div ref={curlOutputRef}>
                                <div className={styles.curlOutputHeader}>
                                    <h4 className={styles.curlOutputTitle}>Generated cURL Command</h4>
                                    <button
                                        type="button"
                                        className={`${styles.copyBtn}${copied ? ' btn-copied' : ''}`}
                                        onClick={copyCurlCommand}
                                    >
                                        {copied ? '✅ Copied!' : '📋 Copy to Clipboard'}
                                    </button>
                                </div>
                                <pre className={styles.curlPre}><code>{curlCommand}</code></pre>

                                <div className={styles.proTip}>
                                    <strong>💡 Pro Tip:</strong>
                                    <p>
                                        Add <code>{'| jq'}</code> to pretty-print JSON output, or
                                        {' '}<code>{`| jq '.results[] | {name: .full_name, title: .job_title}'`}</code> to extract specific fields.
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
                </section>

                {/* Authentication */}
                <section id="authentication" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Authentication</h2>
                    <p className={styles.sectionDescription}>
                        API keys are required for production usage. Include your API key in the <code className={styles.inlineCode}>X-API-Key</code> header.
                    </p>

                    <h3 className={styles.subheading}>API Key Tiers</h3>

                    <table>
                        <thead>
                            <tr>
                                <th>Tier</th>
                                <th>Max Results</th>
                                <th>Rate Limit</th>
                                <th>Features</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Public</td>
                                <td>50</td>
                                <td>60/min</td>
                                <td>Basic search, PII redacted</td>
                            </tr>
                            <tr>
                                <td>Basic</td>
                                <td>200</td>
                                <td>200/min</td>
                                <td>Search + Export (with scope)</td>
                            </tr>
                            <tr>
                                <td>Trusted</td>
                                <td>1000</td>
                                <td>1000/min</td>
                                <td>Full access + PII (with scope)</td>
                            </tr>
                        </tbody>
                    </table>

                    <h3 className={styles.subheading}>Scopes</h3>
                    <ul>
                        <li><code className={styles.inlineCode}>search:read</code> - Basic search access (default)</li>
                        <li><code className={styles.inlineCode}>export:read</code> - CSV/NDJSON export capabilities</li>
                        <li><code className={styles.inlineCode}>pii:read</code> - Access to email, phone, LinkedIn URLs</li>
                    </ul>

                    <div className={styles.infoBox}>
                        <div className={styles.infoBoxTitle}>Example Request</div>
                        <div className={styles.infoBoxContent}>
                            <pre><code>{`curl http://localhost:8000/search?q=engineer \\
  -H "X-API-Key: your-api-key-here"`}</code></pre>
                        </div>
                    </div>
                </section>

                {/* Rate Limits */}
                <section id="rate-limits" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Rate Limits</h2>
                    <p className={styles.sectionDescription}>
                        Rate limits are enforced per IP address (for public) or per API key (for authenticated requests).
                    </p>

                    <table>
                        <thead>
                            <tr>
                                <th>Endpoint</th>
                                <th>Limit</th>
                                <th>Burst</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>/search</td>
                                <td>60/min (public)<br />200/min (basic)<br />1000/min (trusted)</td>
                                <td>120/min</td>
                            </tr>
                            <tr>
                                <td>/export/*</td>
                                <td>6/min</td>
                                <td>10/min</td>
                            </tr>
                            <tr>
                                <td>/filters</td>
                                <td>No limit</td>
                                <td>-</td>
                            </tr>
                        </tbody>
                    </table>

                    <div className={`${styles.infoBox} ${styles.warning}`}>
                        <div className={styles.infoBoxTitle}>⚠️ Rate Limit Headers</div>
                        <div className={styles.infoBoxContent}>
                            When rate limited, you&apos;ll receive a <code className={styles.inlineCode}>429 Too Many Requests</code> response.
                            Retry after the specified time in the <code className={styles.inlineCode}>Retry-After</code> header.
                        </div>
                    </div>
                </section>

                {/* Quick Start */}
                <section id="quick-start" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Quick Start</h2>
                    <p className={styles.sectionDescription}>
                        Get started with the PROSPECTIQ API in 3 simple steps.
                    </p>

                    <h3 className={styles.subheading}>Step 1: Get an API Key</h3>
                    <ol>
                        <li>Go to the <Link href="/dashboard" className={styles.docLink}>API Keys</Link> page</li>
                        <li>Click &quot;Create New Key&quot;</li>
                        <li>Select scopes and tier</li>
                        <li>Copy your API key (shown only once!)</li>
                    </ol>

                    <h3 className={styles.subheading}>Step 2: Make Your First Request</h3>
                    <pre><code>{`curl "http://localhost:8000/search?q=software+engineer&limit=5" \\
  -H "X-API-Key: your-api-key-here"`}</code></pre>

                    <h3 className={styles.subheading}>Step 3: Process the Response</h3>
                    <pre><code>{`{
  "results": [
    {
      "id": "uuid",
      "full_name": "John Doe",
      "job_title": "Senior Software Engineer",
      "company_name": "Tech Corp",
      "location": "San Francisco, CA",
      "skills": ["Python", "React", "AWS"],
      "score": 0.92
    }
  ],
  "total_count": 1247,
  "returned_count": 5,
  "query_time_ms": 423
}`}</code></pre>
                </section>

                {/* Health Endpoint */}
                <section id="health" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Health Check</h2>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/health</span>
                        </div>
                        <p className={styles.endpointDescription}>
                            Check the health status of the API and database connection.
                        </p>

                        <h4 className={styles.blockTitle}>Response</h4>
                        <pre><code>{`{
  "status": "healthy",
  "timestamp": "2025-10-21T03:00:00Z",
  "database": "connected",
  "profiles_total": 497552,
  "profiles_with_embeddings": 0
}`}</code></pre>
                    </div>
                </section>

                {/* Search Endpoint */}
                <section id="search" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Search Profiles</h2>
                    <p className={styles.sectionDescription}>
                        Semantic search with advanced filtering. Supports both GET (query params) and POST (JSON body).
                    </p>

                    {/* GET Search */}
                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/search</span>
                        </div>
                        <p className={styles.endpointDescription}>
                            Search using URL query parameters. Ideal for simple integrations and HTTP request nodes.
                        </p>

                        <h4 className={styles.blockTitle}>Query Parameters</h4>
                        <table>
                            <thead>
                                <tr>
                                    <th>Parameter</th>
                                    <th>Type</th>
                                    <th>Description</th>
                                    <th>Default</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>q</td>
                                    <td>string</td>
                                    <td>Search query (natural language)</td>
                                    <td>&quot;&quot;</td>
                                </tr>
                                <tr>
                                    <td>limit</td>
                                    <td>integer</td>
                                    <td>Results per page (1-1000)</td>
                                    <td>20</td>
                                </tr>
                                <tr>
                                    <td>offset</td>
                                    <td>integer</td>
                                    <td>Pagination offset</td>
                                    <td>0</td>
                                </tr>
                                <tr>
                                    <td>location_country</td>
                                    <td>string</td>
                                    <td>Filter by country</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>regions</td>
                                    <td>array</td>
                                    <td>Filter by regions (repeat param)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>localities</td>
                                    <td>array</td>
                                    <td>Filter by cities (repeat param)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>industries</td>
                                    <td>array</td>
                                    <td>Filter by industries (OR logic)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>skills</td>
                                    <td>array</td>
                                    <td>Required skills (AND logic)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>min_years_experience</td>
                                    <td>integer</td>
                                    <td>Minimum years (0-80)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>max_years_experience</td>
                                    <td>integer</td>
                                    <td>Maximum years (0-80)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>job_title</td>
                                    <td>string</td>
                                    <td>Filter by job title (partial match, case-insensitive)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>company</td>
                                    <td>string</td>
                                    <td>Filter by company name (partial match, case-insensitive)</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_linkedin</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with LinkedIn URL</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_email</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with email address</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_phone</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with phone number</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_website</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with website/domain</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_twitter</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with Twitter handle</td>
                                    <td>-</td>
                                </tr>
                                <tr>
                                    <td>has_github</td>
                                    <td>boolean</td>
                                    <td>Filter profiles with GitHub username</td>
                                    <td>-</td>
                                </tr>
                            </tbody>
                        </table>

                        <h4 className={styles.blockTitle}>Example Request</h4>
                        <pre><code>{`GET /search?q=senior+python+engineer&location_country=united+states&regions=california&skills=python&skills=sql&job_title=software+engineer&has_email=true&limit=20`}</code></pre>
                    </div>

                    {/* POST Search */}
                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodPost}`}>POST</span>
                            <span className={styles.endpointPath}>/search</span>
                        </div>
                        <p className={styles.endpointDescription}>
                            Search using JSON body. Better for complex filters and programmatic access.
                        </p>

                        <h4 className={styles.blockTitle}>Request Body</h4>
                        <pre><code>{`{
  "query": "senior python engineer",
  "limit": 20,
  "offset": 0,
  "location_country": "united states",
  "regions": ["california", "new york"],
  "industries": ["Computer Software", "Internet"],
  "skills": ["python", "sql"],
  "min_years_experience": 5,
  "max_years_experience": 15,
  "job_title": "software engineer",
  "company": "google",
  "has_email": true,
  "has_phone": true,
  "has_linkedin": true
}`}</code></pre>

                        <h4 className={styles.blockTitle}>Response</h4>
                        <pre><code>{`{
  "results": [...],
  "total_count": 1247,
  "returned_count": 20,
  "offset": 0,
  "limit": 20,
  "query_time_ms": 542,
  "query": "senior python engineer",
  "filters_applied": {
    "location_country": "united states",
    "regions": ["california", "new york"],
    "min_experience": 5
  },
  "next_page_token": "eyJxdWVyeSI6..."
}`}</code></pre>
                    </div>
                </section>

                {/* Filter Endpoints */}
                <section id="filters" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Filter Options</h2>
                    <p className={styles.sectionDescription}>
                        Get available filter values for countries, regions, cities, and industries. All filter endpoints are cached for 10 minutes.
                    </p>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/countries</span>
                        </div>
                        <p className={styles.endpointDescription}>List all countries in the database.</p>
                        <pre><code>{`{"countries": ["united states", "canada", ...]}`}</code></pre>
                    </div>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/regions</span>
                        </div>
                        <p className={styles.endpointDescription}>List regions/states, optionally filtered by country.</p>
                        <pre><code>{`GET /regions?country=united+states

{
  "regions": [
    {"region": "california", "count": 12345},
    {"region": "new york", "count": 8765}
  ]
}`}</code></pre>
                    </div>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/localities</span>
                        </div>
                        <p className={styles.endpointDescription}>List cities, optionally filtered by country and region.</p>
                        <pre><code>{`GET /localities?country=united+states&region=california

{
  "localities": [
    {"locality": "san francisco", "count": 2345},
    {"locality": "los angeles", "count": 1876}
  ]
}`}</code></pre>
                    </div>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/industries</span>
                        </div>
                        <p className={styles.endpointDescription}>List all industries.</p>
                        <pre><code>{`{"industries": ["Computer Software", "Internet", "Financial Services", ...]}`}</code></pre>
                    </div>
                </section>

                {/* Export Endpoints */}
                <section id="export" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Export Data</h2>
                    <p className={styles.sectionDescription}>
                        Bulk export search results in CSV or NDJSON format. Requires <code className={styles.inlineCode}>export:read</code> scope.
                    </p>

                    <div className={`${styles.infoBox} ${styles.warning}`}>
                        <div className={styles.infoBoxTitle}>⚠️ Export Requirements</div>
                        <div className={styles.infoBoxContent}>
                            Export endpoints require:
                            <ul>
                                <li>API key with <code className={styles.inlineCode}>export:read</code> scope</li>
                                <li>Non-empty query (<code className={styles.inlineCode}>q</code>) OR at least one filter</li>
                                <li>Maximum 1000 results per request</li>
                            </ul>
                        </div>
                    </div>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/export/csv</span>
                        </div>
                        <p className={styles.endpointDescription}>
                            Export search results as CSV. PII fields redacted unless key has <code className={styles.inlineCode}>pii:read</code> scope.
                        </p>

                        <h4 className={styles.blockTitle}>Example Request</h4>
                        <pre><code>{`GET /export/csv?q=python&limit=1000&regions=california
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="export.csv"

id,full_name,job_title,company_name,industry,location,skills,score
uuid,John Doe,Senior Engineer,Tech Corp,Software,"San Francisco, CA","[Python, SQL]",0.92
...`}</code></pre>
                    </div>

                    <div className={styles.endpoint}>
                        <div className={styles.endpointHeader}>
                            <span className={`${styles.methodBadge} ${styles.methodGet}`}>GET</span>
                            <span className={styles.endpointPath}>/export/ndjson</span>
                        </div>
                        <p className={styles.endpointDescription}>
                            Export search results as NDJSON (newline-delimited JSON). One JSON object per line.
                        </p>

                        <h4 className={styles.blockTitle}>Example Response</h4>
                        <pre><code>{`{"id":"uuid","full_name":"John Doe","job_title":"Senior Engineer",...}
{"id":"uuid","full_name":"Jane Smith","job_title":"Staff Engineer",...}
{"id":"uuid","full_name":"Bob Wilson","job_title":"Principal Engineer",...}`}</code></pre>
                    </div>
                </section>

                {/* Pagination */}
                <section id="pagination" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Pagination</h2>
                    <p className={styles.sectionDescription}>
                        Use offset-based pagination or opaque page tokens for efficient result navigation.
                    </p>

                    <h3 className={styles.subheading}>Offset-Based Pagination</h3>
                    <pre><code>{`// Page 1
GET /search?q=engineer&limit=20&offset=0

// Page 2
GET /search?q=engineer&limit=20&offset=20

// Page 3
GET /search?q=engineer&limit=20&offset=40`}</code></pre>

                    <h3 className={styles.subheading}>Token-Based Pagination</h3>
                    <p className={styles.sectionDescription}>
                        Use <code className={styles.inlineCode}>next_page_token</code> for easier pagination without managing offsets.
                    </p>
                    <pre><code>{`// First request
GET /search?q=python&limit=100

{
  "results": [...],
  "next_page_token": "eyJxdWVyeSI6..."
}

// Next page
GET /search?page_token=eyJxdWVyeSI6...`}</code></pre>
                </section>

                {/* Examples */}
                <section id="examples" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Code Examples</h2>

                    <h3 className={styles.subheading}>cURL</h3>
                    <pre><code>{`curl -G "http://localhost:8000/search" \\
  -H "X-API-Key: your-api-key" \\
  --data-urlencode "q=senior software engineer" \\
  --data-urlencode "location_country=united states" \\
  --data-urlencode "regions=california" \\
  --data-urlencode "skills=python" \\
  --data-urlencode "job_title=software engineer" \\
  --data-urlencode "has_email=true" \\
  --data-urlencode "limit=50"`}</code></pre>

                    <h3 className={styles.subheading}>JavaScript (fetch)</h3>
                    <pre><code>{`const response = await fetch('http://localhost:8000/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    query: 'senior software engineer',
    location_country: 'united states',
    regions: ['california'],
    skills: ['python', 'react'],
    job_title: 'software engineer',
    has_email: true,
    has_linkedin: true,
    limit: 50
  })
});

const data = await response.json();
console.log(\`Found \${data.total_count} results\`);
console.log(data.results);`}</code></pre>

                    <h3 className={styles.subheading}>Python (requests)</h3>
                    <pre><code>{`import requests

response = requests.post('http://localhost:8000/search',
    headers={'X-API-Key': 'your-api-key'},
    json={
        'query': 'senior software engineer',
        'location_country': 'united states',
        'regions': ['california'],
        'skills': ['python', 'react'],
        'job_title': 'software engineer',
        'has_email': True,
        'has_linkedin': True,
        'limit': 50
    }
)

data = response.json()
print(f"Found {data['total_count']} results")
for profile in data['results']:
    print(f"{profile['full_name']} - {profile['job_title']}")`}</code></pre>
                </section>

                {/* Error Handling */}
                <section id="errors" className={styles.docSection}>
                    <h2 className={styles.sectionTitle}>Error Handling</h2>
                    <p className={styles.sectionDescription}>
                        The API uses standard HTTP status codes. All error responses include a JSON body with details.
                    </p>

                    <table>
                        <thead>
                            <tr>
                                <th>Status Code</th>
                                <th>Meaning</th>
                                <th>Common Causes</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>400</td>
                                <td>Bad Request</td>
                                <td>Invalid parameters, malformed JSON</td>
                            </tr>
                            <tr>
                                <td>401</td>
                                <td>Unauthorized</td>
                                <td>Missing or invalid API key</td>
                            </tr>
                            <tr>
                                <td>403</td>
                                <td>Forbidden</td>
                                <td>Insufficient scopes or tier</td>
                            </tr>
                            <tr>
                                <td>422</td>
                                <td>Unprocessable Entity</td>
                                <td>Validation errors, offset too high</td>
                            </tr>
                            <tr>
                                <td>429</td>
                                <td>Too Many Requests</td>
                                <td>Rate limit exceeded</td>
                            </tr>
                            <tr>
                                <td>500</td>
                                <td>Internal Server Error</td>
                                <td>Server-side error</td>
                            </tr>
                        </tbody>
                    </table>

                    <h3 className={styles.subheading}>Error Response Format</h3>
                    <pre><code>{`{
  "error": "Invalid query parameter",
  "detail": "limit must be between 1 and 1000",
  "timestamp": "2025-10-21T03:00:00Z"
}`}</code></pre>
                </section>

                {/* Footer */}
                <div className={styles.footerLinks}>
                    <Link href="/">← Back to Search</Link>
                    <Link href="/dashboard">API Keys</Link>
                    <Link href="/login">Login</Link>
                </div>
            </main>

            {/* Back to Top Button */}
            <button
                type="button"
                className={`${styles.backToTop}${showBackToTop ? ` ${styles.visible}` : ''}`}
                onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            >
                <span>↑</span>
            </button>
        </div>
    );
}
