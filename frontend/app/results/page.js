'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/AppShell';
import { getApiBaseUrl } from '@/lib/config';
import styles from './results.module.css';

function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

function formatFilterKey(key) {
    const keyMap = {
        keyword: 'Keyword',
        country: 'Country',
        industry: 'Industry',
        min_experience: 'Min Experience',
        max_experience: 'Max Experience',
        skills: 'Skills',
    };
    return keyMap[key] || key;
}

function buildSearchQuery(searchParams, offset, limit) {
    // Build GET query params to avoid CORS preflight
    const params = new URLSearchParams();
    params.set('q', searchParams.keyword || '');
    params.set('offset', String(offset));
    params.set('limit', String(limit));
    params.set('vector_weight', '0.8');
    params.set('lexical_weight', '0.2');
    params.set('ef_search', '64');
    // Always US for now
    params.set('location_country', 'united states');

    // Multi-select arrays as repeated params
    (searchParams.states || []).forEach((st) => params.append('regions', st));
    (searchParams.industries || []).forEach((ind) => params.append('industries', ind));

    // Experience
    if (searchParams.min_experience) params.set('min_years_experience', String(parseInt(searchParams.min_experience)));
    if (searchParams.max_experience) params.set('max_years_experience', String(parseInt(searchParams.max_experience)));

    // Skills (comma-separated)
    if (searchParams.skills) {
        searchParams.skills.split(',').map((s) => s.trim()).filter(Boolean).forEach((skill) => params.append('skills', skill));
    }

    // Job Title and Company filters
    if (searchParams.job_title) params.set('job_title', searchParams.job_title);
    if (searchParams.company) params.set('company', searchParams.company);

    // Contact information filters (boolean checkboxes)
    if (searchParams.has_linkedin) params.set('has_linkedin', 'true');
    if (searchParams.has_email) params.set('has_email', 'true');
    if (searchParams.has_phone) params.set('has_phone', 'true');
    if (searchParams.has_website) params.set('has_website', 'true');
    if (searchParams.has_twitter) params.set('has_twitter', 'true');
    if (searchParams.has_github) params.set('has_github', 'true');

    return params;
}

function truncate(text, max) {
    return text.length > max ? text.substring(0, max) + '...' : text;
}

function ProfileRow({ profile }) {
    const location = [profile.locality, profile.region, profile.location_country].filter(Boolean).join(', ') || '—';

    const skillsArray = profile.skills || [];
    const skillsText = Array.isArray(skillsArray) ? skillsArray.join(', ') : String(skillsArray);
    const skills = truncate(skillsText, 100) || '—';

    const summaryFull = profile.summary || '';
    const summaryDisplay = truncate(summaryFull, 150) || '—';

    const linkedinDisplay = profile.linkedin_url ? profile.linkedin_url.replace('linkedin.com/in/', '') : null;

    const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || '—';

    return (
        <tr>
            <td className={styles.nameCell}>{name}</td>
            <td className={styles.capitalize}>{profile.job_title || '—'}</td>
            <td className={styles.capitalize}>{profile.company_name || '—'}</td>
            <td className={styles.capitalize}>{profile.industry || '—'}</td>
            <td className={styles.capitalize}>{location}</td>
            <td>{profile.years_experience !== null ? `${profile.years_experience} yrs` : '—'}</td>
            <td className={styles.summaryCell} title={summaryFull}>{summaryDisplay}</td>
            <td>
                {profile.linkedin_url ? (
                    <a href={`https://${profile.linkedin_url}`} target="_blank" rel="noopener" className="link-accent">{linkedinDisplay}</a>
                ) : '—'}
            </td>
            <td>
                {profile.email ? (
                    <a href={`mailto:${profile.email}`} className="link-accent">{profile.email}</a>
                ) : '—'}
            </td>
            <td>{profile.phone || '—'}</td>
            <td>
                {profile.website ? (
                    <a href={`https://${profile.website}`} target="_blank" rel="noopener" className="link-accent">{profile.website}</a>
                ) : '—'}
            </td>
            <td>
                {profile.twitter ? (
                    <a href={`https://twitter.com/${profile.twitter}`} target="_blank" rel="noopener" className="link-accent">@{profile.twitter}</a>
                ) : '—'}
            </td>
            <td>
                {profile.github ? (
                    <a href={`https://github.com/${profile.github}`} target="_blank" rel="noopener" className="link-accent">{profile.github}</a>
                ) : '—'}
            </td>
            <td className={styles.skillsCell} title={skillsText}>{skills}</td>
        </tr>
    );
}

export default function ResultsPage() {
    const router = useRouter();

    // null until sessionStorage has been read (client-only)
    const [searchParams, setSearchParams] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | results | empty | error
    const [data, setData] = useState(null);
    const [errorMessage, setErrorMessage] = useState('');
    const [offset, setOffset] = useState(0);
    const [limit, setLimit] = useState(100);
    const [totalCount, setTotalCount] = useState(0);
    const requestSeq = useRef(0);

    useEffect(() => {
        const paramsStr = sessionStorage.getItem('searchParams');
        if (!paramsStr) {
            // No search params - redirect to search page
            router.replace('/');
            return;
        }

        const params = JSON.parse(paramsStr);
        setSearchParams(params);
        setOffset(params.offset || 0);
        setLimit(params.limit || 50);
    }, [router]);

    const executeSearch = useCallback(async (params, searchOffset, searchLimit) => {
        const seq = ++requestSeq.current;
        setStatus('loading');

        try {
            const query = buildSearchQuery(params, searchOffset, searchLimit);
            const response = await fetch(`${getApiBaseUrl()}/search?${query.toString()}`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || response.statusText);
            }

            const result = await response.json();
            if (seq !== requestSeq.current) return; // stale response

            setTotalCount(result.total_count);
            setData(result);
            setStatus(result.returned_count === 0 ? 'empty' : 'results');
        } catch (error) {
            console.error('Search error:', error);
            if (seq !== requestSeq.current) return;
            setErrorMessage(error.message);
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        if (!searchParams) return;
        executeSearch(searchParams, offset, limit);
    }, [searchParams, offset, limit, executeSearch]);

    const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

    const goPrev = () => {
        if (offset > 0) {
            setOffset(Math.max(0, offset - limit));
            scrollToTop();
        }
    };

    const goNext = () => {
        if (offset + limit < totalCount) {
            setOffset(offset + limit);
            scrollToTop();
        }
    };

    const changeLimit = (e) => {
        setLimit(parseInt(e.target.value));
        setOffset(0); // Reset to first page
        scrollToTop();
    };

    const goBack = () => window.history.back();

    const exportToCSV = async () => {
        try {
            const params = new URLSearchParams();
            params.set('q', searchParams?.keyword || '');
            params.set('limit', '1000');
            params.set('offset', '0');
            params.set('location_country', 'united states');
            (searchParams?.states || []).forEach((st) => params.append('regions', st));
            (searchParams?.industries || []).forEach((ind) => params.append('industries', ind));
            if (searchParams?.min_experience) params.set('min_years_experience', String(parseInt(searchParams.min_experience)));
            if (searchParams?.max_experience) params.set('max_years_experience', String(parseInt(searchParams.max_experience)));
            if (searchParams?.skills) {
                searchParams.skills.split(',').map((s) => s.trim()).filter(Boolean).forEach((skill) => params.append('skills', skill));
            }

            const resp = await fetch(`${getApiBaseUrl()}/export/csv?${params.toString()}`);
            if (!resp.ok) throw new Error('Failed to export CSV');

            const blob = await resp.blob();
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.href = url;
            link.download = `prospectiq_results_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export error:', error);
            alert('Failed to export CSV: ' + error.message);
        }
    };

    const start = offset + 1;
    const end = data ? Math.min(offset + data.returned_count, totalCount) : 0;
    const currentPage = Math.floor(offset / limit) + 1;
    const totalPages = Math.ceil(totalCount / limit);
    const filtersApplied = data?.filters_applied || {};

    return (
        <AppShell>
            <div className={styles.container}>
                {/* Results Summary */}
                {status === 'results' && data && (
                    <div className={styles.summaryCard}>
                        <div className={styles.summaryTop}>
                            <div>
                                <div className={styles.summaryHeading}>
                                    <h2>{formatNumber(totalCount)} results</h2>
                                    <span
                                        className={`${styles.timeChip} ${data.query_time_ms >= 1000 ? styles.timeChipSlow : ''}`}
                                        title="Query time"
                                    >
                                        {data.query_time_ms.toFixed(0)}ms
                                    </span>
                                </div>
                                {searchParams?.keyword && (
                                    <p className={styles.summaryQuery}>&ldquo;{searchParams.keyword}&rdquo;</p>
                                )}
                            </div>
                            <div className={styles.summaryActions}>
                                <button onClick={() => window.print()} className={styles.actionBtn}>
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M5 17H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-1" />
                                        <path d="M5 21h14a2 2 0 0 0 2-2v-5H3v5a2 2 0 0 0 2 2Z" />
                                    </svg>
                                    Save
                                </button>
                                <button onClick={exportToCSV} className={styles.actionBtnPrimary}>
                                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                        <polyline points="7 10 12 15 17 10" />
                                        <line x1="12" y1="15" x2="12" y2="3" />
                                    </svg>
                                    Export CSV
                                </button>
                            </div>
                        </div>
                        <div className={styles.filterChips}>
                            {Object.keys(filtersApplied).length === 0 ? (
                                <span className={styles.filterChip}>No filters applied</span>
                            ) : (
                                Object.entries(filtersApplied).map(([key, value]) => (
                                    <span className={styles.filterChip} key={key}>
                                        {formatFilterKey(key)}: {String(value)}
                                    </span>
                                ))
                            )}
                        </div>
                    </div>
                )}

                {/* Results Table */}
                <div className={styles.tableCard}>
                    {status === 'results' && data ? (
                        <div className={styles.tableScroll}>
                            <table className={styles.table}>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Job Title</th>
                                        <th>Company</th>
                                        <th>Industry</th>
                                        <th>Location</th>
                                        <th>Experience</th>
                                        <th>Summary</th>
                                        <th>LinkedIn</th>
                                        <th>Email</th>
                                        <th>Phone</th>
                                        <th>Website</th>
                                        <th>Twitter</th>
                                        <th>GitHub</th>
                                        <th>Skills</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.results.map((profile, index) => (
                                        <ProfileRow profile={profile} key={profile.id || index} />
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : status === 'loading' ? (
                        <div className={styles.stateBox}>
                            <div className="spinner"></div>
                            <p className={styles.stateText}>Searching profiles...</p>
                        </div>
                    ) : status === 'empty' ? (
                        <div className={styles.stateBox}>
                            <p className={styles.stateEmoji}>🔍</p>
                            <p className={styles.stateTitle}>No results found</p>
                            <p className={styles.stateText}>Try adjusting your filters or search terms</p>
                            <button onClick={goBack} className={`btn-primary ${styles.stateAction}`}>
                                <span>Back to Search</span>
                            </button>
                        </div>
                    ) : (
                        <div className={styles.stateBox}>
                            <p className={styles.stateEmoji}>⚠️</p>
                            <p className={styles.stateTitle}>Search failed</p>
                            <p className={styles.stateText}>{errorMessage}</p>
                            <button onClick={goBack} className={`btn-primary ${styles.stateAction}`}>
                                <span>Back to Search</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Pagination */}
                <div className={styles.paginationBar}>
                    <div className={styles.paginationInfo}>
                        <span>Rows per page</span>
                        <select className={styles.rowsSelect} value={String(limit)} onChange={changeLimit}>
                            <option value="15">15</option>
                            <option value="20">20</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                        <span className={styles.rangeText}>
                            {totalCount > 0 ? `${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(totalCount)}` : ''}
                        </span>
                    </div>

                    <div className={styles.paginationControls}>
                        <button className={styles.pageBtn} onClick={goPrev} disabled={offset === 0}>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="m15 18-6-6 6-6" />
                            </svg>
                            Previous
                        </button>
                        <button className={styles.pageBtn} onClick={goNext} disabled={offset + limit >= totalCount}>
                            Next
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="m9 18 6-6-6-6" />
                            </svg>
                        </button>
                    </div>

                    <span className={styles.pageInfo}>
                        {totalCount > 0 ? `Page ${currentPage} of ${formatNumber(totalPages)}` : ''}
                    </span>
                </div>
            </div>
        </AppShell>
    );
}
