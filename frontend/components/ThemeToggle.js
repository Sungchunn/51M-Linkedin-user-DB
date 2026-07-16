'use client';

import { useEffect, useState } from 'react';
import { toggleTheme } from '@/lib/theme';

export default function ThemeToggle() {
    // Theme is applied pre-hydration by the layout bootstrap script; track it
    // here only for the accessible label.
    const [theme, setTheme] = useState('dark');

    useEffect(() => {
        setTheme(document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
        const onThemeChange = (event) => setTheme(event.detail.theme);
        window.addEventListener('themechange', onThemeChange);
        return () => window.removeEventListener('themechange', onThemeChange);
    }, []);

    const label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';

    return (
        <button className="theme-toggle" type="button" aria-label={label} title={label} onClick={toggleTheme}>
            <svg className="icon-sun" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></svg>
            <svg className="icon-moon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" /></svg>
        </button>
    );
}
