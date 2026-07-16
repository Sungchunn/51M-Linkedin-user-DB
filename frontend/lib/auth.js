/**
 * Authentication helpers — JWT tokens in localStorage.
 *
 * Client-side only: every function here touches localStorage or
 * window, so call them from event handlers or useEffect.
 */
import { getApiBaseUrl } from './config';

export function isTokenExpired(token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.exp * 1000 < Date.now();
    } catch (e) {
        return true;
    }
}

export function isAuthenticated() {
    const token = localStorage.getItem('access_token');
    return Boolean(token) && !isTokenExpired(token);
}

export function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return {};
    }
    return { Authorization: `Bearer ${token}` };
}

export function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expires_at');
    window.location.href = '/login';
}

export async function login(username, password) {
    const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.detail || 'Login failed');
    }

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_expires_at', Date.now() + data.expires_in * 1000);

    return data;
}

export async function register(username, email, password, fullName) {
    const response = await fetch(`${getApiBaseUrl()}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username,
            email,
            password,
            full_name: fullName || null,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.detail || 'Registration failed');
    }

    return data;
}
