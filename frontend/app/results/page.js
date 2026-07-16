'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Footer from '@/components/Footer';
import Header from '@/components/Header';
import SquaresBackground from '@/components/SquaresBackground';
import { getApiBaseUrl } from '@/lib/config';

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

    return (
        <tr>
            <td>{profile.first_name || '—'}</td>
            <td>{profile.last_name || '—'}</td>
            <td>{profile.job_title || '—'}</td>
            <td>{profile.company_name || '—'}</td>
            <td>{profile.industry || '—'}</td>
            <td>{location}</td>
            <td>{profile.years_experience !== null ? `${profile.years_experience} yrs` : '—'}</td>
            <td title={summaryFull} style={{ maxWidth: 300, whiteSpace: 'normal' }}>{summaryDisplay}</td>
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
            <td title={skillsText}>{skills}</td>
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
        <>
            <SquaresBackground />
            <Header />

            <div className="results-container">
                {/* Results Summary */}
                {status === 'results' && data && (
                    <div className="results-summary">
                        <div className="summary-header">
                            <div>
                                <div className="summary-stats">
                                    <h2>
                                        Showing {formatNumber(start)}-{formatNumber(end)} of {formatNumber(totalCount)} results
                                    </h2>
                                    <span className={data.query_time_ms < 1000 ? 'text-success' : 'text-muted'}>
                                        Query time: {data.query_time_ms.toFixed(0)}ms
                                    </span>
                                </div>
                                <p className="summary-query">{searchParams?.keyword || ''}</p>
                            </div>
                            <div className="summary-actions">
                                <button onClick={() => window.print()} className="btn-secondary">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M5 17H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-1" />
                                        <path d="M5 21h14a2 2 0 0 0 2-2v-5H3v5a2 2 0 0 0 2 2Z" />
                                    </svg>
                                    Save
                                </button>
                                <button onClick={exportToCSV} className="btn-primary">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                        <polyline points="7 10 12 15 17 10" />
                                        <line x1="12" y1="15" x2="12" y2="3" />
                                    </svg>
                                    Export
                                </button>
                            </div>
                        </div>
                        <div id="filtersApplied">
                            {Object.keys(filtersApplied).length === 0 ? (
                                <span className="filter-tag">No filters applied</span>
                            ) : (
                                Object.entries(filtersApplied).map(([key, value]) => (
                                    <span className="filter-tag" key={key}>
                                        {formatFilterKey(key)}: {String(value)}
                                    </span>
                                ))
                            )}
                        </div>
                    </div>
                )}

                {/* Results Table */}
                <div className="table-container">
                    {status === 'results' && data && (
                        <table>
                            <thead>
                                <tr>
                                    <th>FIRST NAME</th>
                                    <th>LAST NAME</th>
                                    <th>JOB TITLE</th>
                                    <th>COMPANY</th>
                                    <th>INDUSTRY</th>
                                    <th>LOCATION</th>
                                    <th>EXPERIENCE</th>
                                    <th>SUMMARY</th>
                                    <th>LINKEDIN</th>
                                    <th>EMAIL</th>
                                    <th>PHONE</th>
                                    <th>WEBSITE</th>
                                    <th>TWITTER</th>
                                    <th>GITHUB</th>
                                    <th>SKILLS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.results.map((profile, index) => (
                                    <ProfileRow profile={profile} key={profile.id || index} />
                                ))}
                            </tbody>
                        </table>
                    )}

                    {status === 'loading' && (
                        <div className="loading-state">
                            <div className="spinner"></div>
                            <p>Searching profiles...</p>
                        </div>
                    )}

                    {status === 'empty' && (
                        <div className="empty-state">
                            <p style={{ fontSize: '3rem', marginBottom: 16 }}>🔍</p>
                            <p style={{ fontSize: '1.25rem', color: 'var(--text-primary)', marginBottom: 8 }}>No results found</p>
                            <p style={{ color: 'var(--text-muted)' }}>Try adjusting your filters or search terms</p>
                            <button onClick={goBack} className="btn-primary" style={{ marginTop: 24 }}>Back to Search</button>
                        </div>
                    )}

                    {status === 'error' && (
                        <div className="error-state">
                            <p style={{ fontSize: '3rem', marginBottom: 16 }}>⚠️</p>
                            <p style={{ fontSize: '1.25rem', color: 'var(--text-primary)', marginBottom: 8 }}>Search failed</p>
                            <p style={{ color: 'var(--text-muted)' }}>{errorMessage}</p>
                            <button onClick={goBack} className="btn-primary" style={{ marginTop: 24 }}>Back to Search</button>
                        </div>
                    )}
                </div>

                {/* Pagination */}
                <div className="pagination">
                    <div className="pagination-info">
                        <span>Rows per page</span>
                        <select
                            className="form-control"
                            style={{ width: 80, padding: '8px 12px', fontSize: '0.875rem' }}
                            value={String(limit)}
                            onChange={changeLimit}
                        >
                            <option value="15">15</option>
                            <option value="20">20</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                        <span style={{ color: 'var(--text-subtle)' }}>
                            {totalCount > 0 ? `${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(totalCount)}` : ''}
                        </span>
                    </div>

                    <div className="pagination-controls">
                        <button onClick={goPrev} disabled={offset === 0}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="m15 18-6-6 6-6" />
                            </svg>
                            Previous
                        </button>
                        <button onClick={goNext} disabled={offset + limit >= totalCount}>
                            Next
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="m9 18 6-6-6-6" />
                            </svg>
                        </button>
                    </div>

                    <span id="pageInfo">
                        {totalCount > 0 ? `Page ${currentPage} of ${formatNumber(totalPages)}` : ''}
                    </span>
                </div>
            </div>

            <Footer />
        </>
    );
}
