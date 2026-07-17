'use client';

/**
 * AppShell — shared chrome for the search experience: SideRays background,
 * collapsible sidebar (brand, New Search, filterable search history, nav,
 * GitHubStars, ThemeToggle) and the main content pane.
 *
 * Sidebar behavior: hideable on desktop (persisted via localStorage
 * 'sidebarCollapsed', floating reopen button) and an off-canvas slide-over
 * on ≤900px. Clicking a history entry re-runs that search.
 */
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GitHubStars from '@/components/GitHubStars';
import SideRays from '@/components/SideRays';
import ThemeToggle from '@/components/ThemeToggle';
import { logout } from '@/lib/auth';
import { addHistoryEntry, clearHistory, getHistory, removeHistoryEntry } from '@/lib/searchHistory';
import styles from './AppShell.module.css';

const SIDEBAR_COLLAPSED_KEY = 'sidebarCollapsed';

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

export default function AppShell({ children, mainClassName = '', onNewSearch }) {
    const router = useRouter();

    const [sidebarOpen, setSidebarOpen] = useState(false); // mobile slide-over
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false); // desktop
    const [history, setHistory] = useState([]);
    const [historyQuery, setHistoryQuery] = useState('');

    // Ray colors come from the --rays-* theme tokens so both modes are covered;
    // re-read on themechange (dispatched by the layout.js theme bootstrap).
    const [rays, setRays] = useState(null);

    useEffect(() => {
        setHistory(getHistory());
        try {
            setSidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true');
        } catch (e) { /* localStorage unavailable */ }

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

    const handleNewSearch = () => {
        setSidebarOpen(false);
        if (onNewSearch) {
            onNewSearch();
        } else {
            router.push('/');
        }
    };

    const handleHistoryRerun = (entry) => {
        setSidebarOpen(false);
        addHistoryEntry(entry.params);
        sessionStorage.setItem('searchParams', JSON.stringify({ ...entry.params, offset: 0, limit: 100 }));
        if (window.location.pathname === '/results') {
            window.location.reload(); // results page re-reads sessionStorage on mount
        } else {
            router.push('/results');
        }
    };

    const handleHistoryDelete = (id) => {
        removeHistoryEntry(id);
        setHistory(getHistory());
    };

    const handleHistoryClear = () => {
        clearHistory();
        setHistory([]);
    };

    const q = historyQuery.trim().toLowerCase();
    const filteredHistory = q ? history.filter((entry) => entry.label.toLowerCase().includes(q)) : history;

    return (
        <div className={styles.shell}>
            {rays && (
                <div className={styles.raysBackground} aria-hidden="true">
                    <SideRays
                        speed={2.5}
                        rayColor1={rays.color1}
                        rayColor2={rays.color2}
                        intensity={2.4}
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

            <main className={`${styles.main} ${mainClassName}`.trim()}>{children}</main>
        </div>
    );
}
