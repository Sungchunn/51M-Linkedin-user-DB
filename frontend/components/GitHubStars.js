'use client';

import { useEffect, useState } from 'react';

const GITHUB_REPO = 'Sungchunn/51M-Linkedin-user-DB';
const CACHE_KEY = 'github_stars_cache';
const CACHE_DURATION = 10 * 60 * 1000; // 10 minutes

function formatStarCount(count) {
    if (count >= 1000) {
        return (count / 1000).toFixed(1) + 'k';
    }
    return count.toString();
}

function getCachedStars() {
    try {
        const cached = localStorage.getItem(CACHE_KEY);
        if (!cached) return null;

        const data = JSON.parse(cached);
        if (Date.now() - data.timestamp < CACHE_DURATION) {
            return data.count;
        }

        localStorage.removeItem(CACHE_KEY);
        return null;
    } catch (e) {
        return null;
    }
}

function setCachedStars(count) {
    try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ count, timestamp: Date.now() }));
    } catch (e) {
        // Ignore localStorage errors
    }
}

async function fetchStarCount() {
    try {
        const response = await fetch(`https://api.github.com/repos/${GITHUB_REPO}`, {
            headers: { Accept: 'application/vnd.github.v3+json' },
        });

        if (!response.ok) {
            throw new Error('GitHub API request failed');
        }

        const data = await response.json();
        return data.stargazers_count || 0;
    } catch (error) {
        console.error('Failed to fetch GitHub stars:', error);
        return null;
    }
}

/**
 * GitHub star counter. variant="inline" renders the header badge,
 * variant="floating" the card version. Hidden until the count loads;
 * stays hidden if the GitHub API is unreachable.
 */
export default function GitHubStars({ variant = 'inline', style }) {
    const [count, setCount] = useState(null);

    useEffect(() => {
        let cancelled = false;

        const cached = getCachedStars();
        if (cached !== null) {
            setCount(cached);
            return undefined;
        }

        fetchStarCount().then((fetched) => {
            if (cancelled || fetched === null) return;
            setCachedStars(fetched);
            setCount(fetched);
        });

        return () => {
            cancelled = true;
        };
    }, []);

    if (count === null) return null;

    if (variant === 'inline') {
        return (
            <span style={style}>
                <a href={`https://github.com/${GITHUB_REPO}`} target="_blank" rel="noopener noreferrer" className="github-badge">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                    </svg>
                    <span className="count">{formatStarCount(count)}</span>
                </a>
            </span>
        );
    }

    return (
        <div style={{ display: 'block', ...style }}>
            <a href={`https://github.com/${GITHUB_REPO}`} target="_blank" rel="noopener noreferrer" className="github-star-link">
                <svg className="github-star-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
                <span className="github-star-count">{formatStarCount(count)}</span>
            </a>
        </div>
    );
}
