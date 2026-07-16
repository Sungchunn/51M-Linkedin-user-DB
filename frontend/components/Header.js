'use client';

import Link from 'next/link';
import GitHubStars from '@/components/GitHubStars';
import ThemeToggle from '@/components/ThemeToggle';
import { logout } from '@/lib/auth';

export default function Header() {
    return (
        <header>
            <div className="header-inner">
                <div>
                    <h1><Link href="/">PROSPECTIQ</Link></h1>
                    <p className="subtitle">Intelligence-Driven Prospecting</p>
                </div>
                <div className="header-right">
                    <Link href="/dashboard" className="nav-link" style={{ fontSize: '0.9rem' }}>API Keys</Link>
                    <Link href="/api-docs" className="nav-link" style={{ fontSize: '0.9rem' }}>API Docs</Link>
                    <GitHubStars variant="inline" />
                    <ThemeToggle />
                    <a
                        href="/login"
                        className="nav-link"
                        style={{ fontSize: '0.9rem' }}
                        onClick={(e) => {
                            e.preventDefault();
                            logout();
                        }}
                    >
                        Logout
                    </a>
                </div>
            </div>
        </header>
    );
}
