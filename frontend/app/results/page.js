'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/AppShell';
import { getApiBaseUrl } from '@/lib/config';
import styles from './results.module.css';

function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

const CONTACT_LABELS = {
    has_linkedin: 'LinkedIn',
    has_email: 'Email',
    has_phone: 'Phone',
    has_website: 'Website',
    has_twitter: 'Twitter',
    has_github: 'GitHub',
};

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
    for (const key of Object.keys(CONTACT_LABELS)) {
        if (searchParams[key]) params.set(key, 'true');
    }

    return params;
}

const ICONS = {
    sliders: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6h16M7 12h10M10 18h4" />
        </svg>
    ),
    save: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <path d="M17 21v-8H7v8M7 3v5h8" />
        </svg>
    ),
    download: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
        </svg>
    ),
    linkedin: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0-.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-.95 1.83-1.95 3.77-1.95 4.03 0 4.78 2.6 4.78 6V21h-4v-5.4c0-1.3-.02-2.96-1.8-2.96-1.8 0-2.08 1.4-2.08 2.86V21H9z" />
        </svg>
    ),
    copy: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="12" height="12" rx="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
    ),
    check: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
        </svg>
    ),
    close: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
        </svg>
    ),
    external: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        </svg>
    ),
    mail: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <path d="m22 7-10 5L2 7" />
        </svg>
    ),
    phone: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.6a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.5-1.1a2 2 0 0 1 2.1-.5c.8.3 1.7.5 2.6.6a2 2 0 0 1 1.7 2z" />
        </svg>
    ),
    globe: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
    ),
    twitter: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z" />
        </svg>
    ),
    github: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
        </svg>
    ),
    prev: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
        </svg>
    ),
    next: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m9 18 6-6-6-6" />
        </svg>
    ),
    chipX: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
        </svg>
    ),
};

function profileName(profile) {
    return [profile.first_name, profile.last_name].filter(Boolean).join(' ') || '—';
}

function profileLocation(profile) {
    return [profile.locality, profile.region, profile.location_country].filter(Boolean).join(', ') || '—';
}

function initialsOf(name) {
    const parts = name.trim().split(/\s+/).filter((p) => /[a-z0-9]/i.test(p));
    if (parts.length === 0) return '·';
    const first = parts[0][0];
    const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
    return (first + last).toUpperCase();
}

/** One result row: identity, company, location, experience, summary, actions. */
function ResultRow({ profile, rowKey, onOpen, onCopy, copied }) {
    const name = profileName(profile);
    return (
        <div
            className={styles.gridRow}
            role="button"
            tabIndex={0}
            onClick={() => onOpen(profile)}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpen(profile);
                }
            }}
        >
            <div className={styles.nameCell}>
                <span className={styles.avatar} aria-hidden="true">{initialsOf(name)}</span>
                <span className={styles.nameStack}>
                    <span className={styles.nameText}>{name}</span>
                    <span className={styles.roleText}>{profile.job_title || '—'}</span>
                </span>
            </div>
            <span className={styles.companyCell}>{profile.company_name || '—'}</span>
            <span className={styles.locationCell}>{profileLocation(profile)}</span>
            <span className={styles.expCell}>
                {profile.years_experience != null ? `${profile.years_experience} yrs` : '—'}
            </span>
            <span className={styles.summaryCell}>{profile.summary || '—'}</span>
            <div className={styles.rowActions}>
                {profile.linkedin_url && (
                    <a
                        className={styles.iconBtn}
                        href={`https://${profile.linkedin_url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open LinkedIn"
                        aria-label="Open LinkedIn profile"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {ICONS.linkedin}
                    </a>
                )}
                <button
                    type="button"
                    className={styles.iconBtn}
                    title={copied ? 'Copied!' : 'Copy contact'}
                    aria-label="Copy contact"
                    onClick={(e) => {
                        e.stopPropagation();
                        onCopy(profile, rowKey);
                    }}
                >
                    {copied ? ICONS.check : ICONS.copy}
                </button>
            </div>
        </div>
    );
}

/** Right-hand slide-over with the full contact profile. */
function ProfileDrawer({ profile, open, onClose }) {
    const [copiedField, setCopiedField] = useState(null);
    const copyTimer = useRef(null);

    useEffect(() => () => clearTimeout(copyTimer.current), []);

    useEffect(() => {
        if (!open) return undefined;
        const onKey = (e) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', onKey);
        document.body.style.overflow = 'hidden';
        return () => {
            document.removeEventListener('keydown', onKey);
            document.body.style.overflow = '';
        };
    }, [open, onClose]);

    const copyValue = (field, text) => {
        navigator.clipboard?.writeText(text).then(() => {
            setCopiedField(field);
            clearTimeout(copyTimer.current);
            copyTimer.current = setTimeout(() => setCopiedField(null), 1400);
        }).catch((error) => console.error('Clipboard copy failed:', error));
    };

    const name = profile ? profileName(profile) : '';
    const skills = profile && Array.isArray(profile.skills) ? profile.skills.filter(Boolean) : [];
    const contactRows = profile ? [
        profile.linkedin_url && {
            field: 'linkedin', icon: ICONS.linkedin, value: profile.linkedin_url,
            href: `https://${profile.linkedin_url}`,
        },
        profile.email && { field: 'email', icon: ICONS.mail, value: profile.email, copyable: true },
        profile.phone && { field: 'phone', icon: ICONS.phone, value: profile.phone, copyable: true },
        profile.website && {
            field: 'website', icon: ICONS.globe, value: profile.website,
            href: `https://${profile.website}`,
        },
        profile.twitter && {
            field: 'twitter', icon: ICONS.twitter, value: `@${profile.twitter}`,
            href: `https://twitter.com/${profile.twitter}`,
        },
        profile.github && {
            field: 'github', icon: ICONS.github, value: profile.github,
            href: `https://github.com/${profile.github}`,
        },
    ].filter(Boolean) : [];

    return (
        <>
            <div
                className={`${styles.scrim} ${open ? styles.scrimOpen : ''}`}
                onClick={onClose}
                aria-hidden="true"
            />
            <aside
                className={`${styles.drawer} ${open ? styles.drawerOpen : ''}`}
                role="dialog"
                aria-modal="true"
                aria-label="Contact profile"
            >
                {profile && (
                    <>
                        <div className={styles.drawerHead}>
                            <span className={styles.drawerHeadLabel}>Contact profile</span>
                            <button
                                type="button"
                                className={styles.iconBtn}
                                title="Close"
                                aria-label="Close profile"
                                onClick={onClose}
                            >
                                {ICONS.close}
                            </button>
                        </div>

                        <div className={styles.drawerBand}>
                            <span className={styles.drawerAvatar} aria-hidden="true">{initialsOf(name)}</span>
                            <div className={styles.drawerIdentity}>
                                <h1 className={styles.drawerName}>{name}</h1>
                                <p className={styles.drawerRole}>
                                    {[profile.job_title, profile.company_name].filter(Boolean).join(' · ') || '—'}
                                </p>
                                <div className={styles.drawerChips}>
                                    {profile.industry && <span className={styles.drawerChip}>{profile.industry}</span>}
                                    {profile.years_experience != null && (
                                        <span className={styles.drawerChip}>{profile.years_experience} yrs experience</span>
                                    )}
                                    <span className={styles.drawerChip}>{profileLocation(profile)}</span>
                                </div>
                            </div>
                            <div className={styles.drawerActions}>
                                {profile.linkedin_url && (
                                    <a
                                        className={styles.drawerPrimaryBtn}
                                        href={`https://${profile.linkedin_url}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        {ICONS.linkedin}
                                        LinkedIn
                                    </a>
                                )}
                                {profile.email && (
                                    <button
                                        type="button"
                                        className={styles.drawerOutlineBtn}
                                        onClick={() => copyValue('headerEmail', profile.email)}
                                    >
                                        {copiedField === 'headerEmail' ? ICONS.check : ICONS.copy}
                                        {copiedField === 'headerEmail' ? 'Copied' : 'Copy email'}
                                    </button>
                                )}
                            </div>
                        </div>

                        {profile.summary && (
                            <div className={styles.drawerSection}>
                                <div className={styles.drawerLabel}>Summary</div>
                                <p className={styles.drawerSummary}>{profile.summary}</p>
                            </div>
                        )}

                        {(profile.job_title || profile.company_name) && (
                            <div className={styles.drawerSection}>
                                <div className={styles.drawerLabel}>Experience</div>
                                <div className={styles.timelineItem}>
                                    <span className={styles.timelineDot} aria-hidden="true" />
                                    <div>
                                        <div className={styles.timelineTitle}>{profile.job_title || '—'}</div>
                                        <div className={styles.timelineSub}>
                                            {[
                                                profile.company_name,
                                                profile.years_experience != null ? `${profile.years_experience} yrs` : null,
                                            ].filter(Boolean).join(' · ') || '—'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {contactRows.length > 0 && (
                            <div className={styles.drawerSection}>
                                <div className={styles.drawerLabel}>Contact</div>
                                <div className={styles.contactList}>
                                    {contactRows.map((row) => (
                                        <div className={styles.contactRow} key={row.field}>
                                            <span className={styles.contactIcon}>{row.icon}</span>
                                            <span className={styles.contactValue}>{row.value}</span>
                                            {row.copyable ? (
                                                <button
                                                    type="button"
                                                    className={styles.contactAction}
                                                    title={copiedField === row.field ? 'Copied!' : 'Copy'}
                                                    aria-label={`Copy ${row.field}`}
                                                    onClick={() => copyValue(row.field, row.value)}
                                                >
                                                    {copiedField === row.field ? ICONS.check : ICONS.copy}
                                                </button>
                                            ) : (
                                                <a
                                                    className={styles.contactAction}
                                                    href={row.href}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    title="Open"
                                                    aria-label={`Open ${row.field}`}
                                                >
                                                    {ICONS.external}
                                                </a>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {skills.length > 0 && (
                            <div className={styles.drawerSection}>
                                <div className={styles.drawerLabel}>Skills</div>
                                <div className={styles.skillCloud}>
                                    {skills.map((skill) => (
                                        <span className={styles.skillChip} key={skill}>{skill}</span>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className={styles.drawerSection}>
                            <div className={styles.drawerLabel}>Details</div>
                            <div className={styles.detailList}>
                                <div className={styles.detailRow}>
                                    <span className={styles.detailKey}>Location</span>
                                    <span className={styles.detailVal}>{profileLocation(profile)}</span>
                                </div>
                                <div className={styles.detailRow}>
                                    <span className={styles.detailKey}>Industry</span>
                                    <span className={styles.detailVal}>{profile.industry || '—'}</span>
                                </div>
                                <div className={styles.detailRow}>
                                    <span className={styles.detailKey}>Experience</span>
                                    <span className={styles.detailVal}>
                                        {profile.years_experience != null ? `${profile.years_experience} yrs` : '—'}
                                    </span>
                                </div>
                                <div className={styles.detailRow}>
                                    <span className={styles.detailKey}>Company</span>
                                    <span className={styles.detailVal}>{profile.company_name || '—'}</span>
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </aside>
        </>
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
    const [limit, setLimit] = useState(200);
    const [totalCount, setTotalCount] = useState(0);
    const requestSeq = useRef(0);

    // Detail slide-over + per-row copy feedback
    const [selected, setSelected] = useState(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [copiedRow, setCopiedRow] = useState(null);
    const copyTimer = useRef(null);

    useEffect(() => () => clearTimeout(copyTimer.current), []);

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
        setLimit(params.limit || 200);
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

    const openProfile = (profile) => {
        setSelected(profile);
        setDrawerOpen(true);
    };

    const closeDrawer = useCallback(() => setDrawerOpen(false), []);

    const copyContact = (profile, rowKey) => {
        const text = profile.email
            || (profile.linkedin_url ? `https://${profile.linkedin_url}` : '')
            || profile.phone
            || profileName(profile);
        navigator.clipboard?.writeText(text).then(() => {
            setCopiedRow(rowKey);
            clearTimeout(copyTimer.current);
            copyTimer.current = setTimeout(() => setCopiedRow(null), 1400);
        }).catch((error) => console.error('Clipboard copy failed:', error));
    };

    // Drop or narrow one filter, persist, and re-run from page 1.
    const removeFilter = (mutate) => {
        setSearchParams((prev) => {
            if (!prev) return prev;
            const next = { ...prev };
            mutate(next);
            try {
                sessionStorage.setItem('searchParams', JSON.stringify({ ...next, offset: 0, limit }));
            } catch (e) { /* sessionStorage unavailable */ }
            return next;
        });
        setOffset(0);
    };

    const filterChips = [];
    if (searchParams) {
        filterChips.push({ id: 'location', label: 'location: United States' }); // always applied
        if (searchParams.keyword) {
            filterChips.push({
                id: 'keyword',
                label: `keyword: ${searchParams.keyword}`,
                remove: () => removeFilter((n) => { delete n.keyword; }),
            });
        }
        if (searchParams.job_title) {
            filterChips.push({
                id: 'job_title',
                label: `title: ${searchParams.job_title}`,
                remove: () => removeFilter((n) => { delete n.job_title; }),
            });
        }
        if (searchParams.company) {
            filterChips.push({
                id: 'company',
                label: `company: ${searchParams.company}`,
                remove: () => removeFilter((n) => { delete n.company; }),
            });
        }
        if (searchParams.min_experience) {
            filterChips.push({
                id: 'min_experience',
                label: `min exp: ${searchParams.min_experience} yrs`,
                remove: () => removeFilter((n) => { delete n.min_experience; }),
            });
        }
        if (searchParams.max_experience) {
            filterChips.push({
                id: 'max_experience',
                label: `max exp: ${searchParams.max_experience} yrs`,
                remove: () => removeFilter((n) => { delete n.max_experience; }),
            });
        }
        const skillList = (searchParams.skills || '').split(',').map((s) => s.trim()).filter(Boolean);
        skillList.forEach((skill) => {
            filterChips.push({
                id: `skill-${skill}`,
                label: `skill: ${skill}`,
                remove: () => removeFilter((n) => {
                    const rest = skillList.filter((s) => s !== skill);
                    if (rest.length) n.skills = rest.join(', ');
                    else delete n.skills;
                }),
            });
        });
        (searchParams.states || []).forEach((state) => {
            filterChips.push({
                id: `state-${state}`,
                label: `state: ${state}`,
                remove: () => removeFilter((n) => {
                    n.states = n.states.filter((s) => s !== state);
                    if (!n.states.length) delete n.states;
                }),
            });
        });
        (searchParams.industries || []).forEach((industry) => {
            filterChips.push({
                id: `industry-${industry}`,
                label: `industry: ${industry}`,
                remove: () => removeFilter((n) => {
                    n.industries = n.industries.filter((i) => i !== industry);
                    if (!n.industries.length) delete n.industries;
                }),
            });
        });
        for (const [key, label] of Object.entries(CONTACT_LABELS)) {
            if (searchParams[key]) {
                filterChips.push({
                    id: key,
                    label: `has: ${label}`,
                    remove: () => removeFilter((n) => { delete n[key]; }),
                });
            }
        }
    }

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

    return (
        <AppShell>
            <div className={styles.container}>
                {/* Header: count + actions */}
                <div className={styles.resultsHeader}>
                    <div className={styles.resultsCountRow}>
                        <span className={styles.resultsCount}>
                            {data ? formatNumber(totalCount) : '—'}
                        </span>
                        <span className={styles.resultsWord}>results</span>
                        {data && (
                            <span className={styles.timeChip} title="Query time">
                                {data.query_time_ms.toFixed(0)}ms
                            </span>
                        )}
                    </div>
                    <div className={styles.headerActions}>
                        <button onClick={() => router.push('/')} className={styles.actionBtn}>
                            {ICONS.sliders}
                            Edit search
                        </button>
                        <button onClick={() => window.print()} className={styles.actionBtn}>
                            {ICONS.save}
                            Save
                        </button>
                        <button onClick={exportToCSV} className={styles.actionBtnPrimary}>
                            {ICONS.download}
                            Export CSV
                        </button>
                    </div>
                </div>

                {/* Active filter chips */}
                {filterChips.length > 0 && (
                    <div className={styles.filterChipsRow}>
                        <span className={styles.filterChipsLabel}>Filters</span>
                        {filterChips.map((chip) => (
                            <span className={styles.filterChip} key={chip.id}>
                                {chip.label}
                                {chip.remove && (
                                    <button
                                        type="button"
                                        className={styles.filterChipX}
                                        aria-label={`Remove filter ${chip.label}`}
                                        onClick={chip.remove}
                                    >
                                        {ICONS.chipX}
                                    </button>
                                )}
                            </span>
                        ))}
                    </div>
                )}

                {/* Results table */}
                <div className={styles.tableCard}>
                    {status === 'results' && data ? (
                        <>
                            <div className={styles.tableScroll}>
                                <div className={styles.tableInner}>
                                    <div className={styles.gridHead}>
                                        <span className={styles.headCell}>Name &amp; role</span>
                                        <span className={styles.headCell}>Company</span>
                                        <span className={styles.headCell}>Location</span>
                                        <span className={styles.headCell}>Exp</span>
                                        <span className={styles.headCell}>Summary</span>
                                        <span className={`${styles.headCell} ${styles.headCellRight}`}>Actions</span>
                                    </div>
                                    {data.results.map((profile, index) => {
                                        const rowKey = profile.id || index;
                                        return (
                                            <ResultRow
                                                profile={profile}
                                                rowKey={rowKey}
                                                key={rowKey}
                                                onOpen={openProfile}
                                                onCopy={copyContact}
                                                copied={copiedRow === rowKey}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                            <div className={styles.tableFooter}>
                                <div className={styles.paginationInfo}>
                                    <span>Rows</span>
                                    <select className={styles.rowsSelect} value={String(limit)} onChange={changeLimit}>
                                        <option value="15">15</option>
                                        <option value="20">20</option>
                                        <option value="50">50</option>
                                        <option value="100">100</option>
                                        <option value="200">200</option>
                                    </select>
                                    <span className={styles.rangeText}>
                                        {totalCount > 0 ? `${formatNumber(start)}–${formatNumber(end)} of ${formatNumber(totalCount)}` : ''}
                                    </span>
                                </div>
                                <div className={styles.paginationControls}>
                                    <button className={styles.pageBtn} onClick={goPrev} disabled={offset === 0}>
                                        {ICONS.prev}
                                        Prev
                                    </button>
                                    <button className={styles.pageBtn} onClick={goNext} disabled={offset + limit >= totalCount}>
                                        Next
                                        {ICONS.next}
                                    </button>
                                    <span className={styles.pageInfo}>
                                        {totalCount > 0 ? `Page ${formatNumber(currentPage)} of ${formatNumber(totalPages)}` : ''}
                                    </span>
                                </div>
                            </div>
                        </>
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

                {status === 'results' && (
                    <p className={styles.tipLine}>Tip — click any row to open the full contact profile.</p>
                )}
            </div>

            <ProfileDrawer profile={selected} open={drawerOpen} onClose={closeDrawer} />
        </AppShell>
    );
}
