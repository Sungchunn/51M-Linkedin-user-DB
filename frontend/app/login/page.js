'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GitHubStars from '@/components/GitHubStars';
import SquaresBackground from '@/components/SquaresBackground';
import ThemeToggle from '@/components/ThemeToggle';
import { isAuthenticated, login, register } from '@/lib/auth';
import styles from './login.module.css';

export default function LoginPage() {
    const router = useRouter();

    const [isLoginMode, setIsLoginMode] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [alert, setAlert] = useState(null); // { message, type: 'error' | 'success' }

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const redirectTimer = useRef(null);

    // Already logged in? Straight to the dashboard.
    useEffect(() => {
        if (isAuthenticated()) {
            router.replace('/dashboard');
        }
        return () => clearTimeout(redirectTimer.current);
    }, [router]);

    const toggleMode = () => {
        setIsLoginMode((mode) => !mode);
        setAlert(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const trimmedUsername = username.trim();
        if (!trimmedUsername || !password) {
            setAlert({ message: 'Please fill in all required fields', type: 'error' });
            return;
        }

        setSubmitting(true);

        try {
            if (isLoginMode) {
                await login(trimmedUsername, password);
                setAlert({ message: 'Login successful! Redirecting...', type: 'success' });
                redirectTimer.current = setTimeout(() => router.push('/dashboard'), 1000);
                return; // keep the button disabled while redirecting
            }

            const trimmedEmail = email.trim();
            if (!trimmedEmail) {
                setAlert({ message: 'Email is required for registration', type: 'error' });
                setSubmitting(false);
                return;
            }
            if (password !== confirmPassword) {
                setAlert({ message: 'Passwords do not match', type: 'error' });
                setSubmitting(false);
                return;
            }
            if (password.length < 8) {
                setAlert({ message: 'Password must be at least 8 characters long', type: 'error' });
                setSubmitting(false);
                return;
            }

            await register(trimmedUsername, trimmedEmail, password, fullName.trim());
            setAlert({ message: 'Account created successfully! Please sign in.', type: 'success' });

            redirectTimer.current = setTimeout(() => {
                setIsLoginMode(true);
                setPassword('');
                setSubmitting(false);
            }, 2000);
        } catch (error) {
            console.error('Auth error:', error);
            setAlert({ message: error.message || 'An error occurred. Please try again.', type: 'error' });
            setSubmitting(false);
        }
    };

    const submitLabel = submitting
        ? (isLoginMode ? 'Signing In...' : 'Creating Account...')
        : (isLoginMode ? 'Sign In' : 'Sign Up');

    return (
        <>
            <SquaresBackground />
            <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 100, display: 'flex', alignItems: 'center', gap: 12 }}>
                <ThemeToggle />
                <GitHubStars variant="floating" />
            </div>
            <div className={styles.loginContainer}>
                <div className={styles.loginCard}>
                    <div className={styles.loginHeader}>
                        <div className={styles.loginLogo}>PROSPECTIQ</div>
                        <div className={styles.loginSubtitle}>
                            {isLoginMode ? 'Sign in to your account' : 'Create a new account'}
                        </div>
                    </div>

                    {alert && (
                        <div className={`${styles.alert} ${alert.type === 'error' ? styles.alertError : styles.alertSuccess}`}>
                            {alert.message}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        {!isLoginMode && (
                            <div className={styles.formGroup}>
                                <label className={styles.formLabel} htmlFor="fullName">Full Name</label>
                                <input
                                    type="text"
                                    id="fullName"
                                    className={styles.formInput}
                                    placeholder="John Doe"
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                />
                            </div>
                        )}

                        {!isLoginMode && (
                            <div className={styles.formGroup}>
                                <label className={styles.formLabel} htmlFor="email">Email</label>
                                <input
                                    type="email"
                                    id="email"
                                    className={styles.formInput}
                                    placeholder="you@example.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                />
                            </div>
                        )}

                        <div className={styles.formGroup}>
                            <label className={styles.formLabel} htmlFor="username">Username</label>
                            <input
                                type="text"
                                id="username"
                                className={styles.formInput}
                                placeholder="Enter your username"
                                required
                                autoFocus
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                            />
                        </div>

                        <div className={styles.formGroup}>
                            <label className={styles.formLabel} htmlFor="password">Password</label>
                            <input
                                type="password"
                                id="password"
                                className={styles.formInput}
                                placeholder="Enter your password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>

                        {!isLoginMode && (
                            <div className={styles.formGroup}>
                                <label className={styles.formLabel} htmlFor="confirmPassword">Confirm Password</label>
                                <input
                                    type="password"
                                    id="confirmPassword"
                                    className={styles.formInput}
                                    placeholder="Re-enter your password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                />
                            </div>
                        )}

                        <button type="submit" className={styles.loginButton} disabled={submitting}>
                            {submitLabel}
                        </button>
                    </form>

                    <div className={styles.toggleMode}>
                        <button type="button" className={styles.toggleButton} onClick={toggleMode}>
                            {isLoginMode ? (
                                <span>Don&apos;t have an account? <strong>Sign up</strong></span>
                            ) : (
                                <span>Already have an account? <strong>Sign in</strong></span>
                            )}
                        </button>
                    </div>

                    <div className={styles.formFooter}>
                        <p className={styles.formFooterText}>
                            <Link href="/" className={styles.formFooterLink}>← Back to Search</Link>
                        </p>
                    </div>
                </div>
            </div>
        </>
    );
}
