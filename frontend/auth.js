// PROSPECTIQ - Authentication JavaScript
// Handles login, registration, and authentication state

const API_BASE_URL = 'http://localhost:8000';

// Check if already logged in
if (window.location.pathname === '/login.html') {
    const token = localStorage.getItem('access_token');
    if (token && !isTokenExpired(token)) {
        // Already logged in, redirect to dashboard
        window.location.href = 'dashboard.html';
    }
}

// Authentication state
let isLoginMode = true;

// DOM elements
const authForm = document.getElementById('authForm');
const toggleMode = document.getElementById('toggleMode');
const submitBtn = document.getElementById('submitBtn');
const alertBox = document.getElementById('alertBox');
const modeSubtitle = document.getElementById('modeSubtitle');
const fullNameGroup = document.getElementById('fullNameGroup');
const emailGroup = document.getElementById('emailGroup');

// Toggle between login and register
toggleMode.addEventListener('click', () => {
    isLoginMode = !isLoginMode;
    updateFormMode();
});

function updateFormMode() {
    const toggleText = document.getElementById('toggleText');
    if (isLoginMode) {
        modeSubtitle.textContent = 'Sign in to your account';
        submitBtn.textContent = 'Sign In';
        toggleText.innerHTML = "Don't have an account? <strong>Sign up</strong>";
        fullNameGroup.style.display = 'none';
        emailGroup.style.display = 'none';
    } else {
        modeSubtitle.textContent = 'Create a new account';
        submitBtn.textContent = 'Sign Up';
        toggleText.innerHTML = 'Already have an account? <strong>Sign in</strong>';
        fullNameGroup.style.display = 'block';
        emailGroup.style.display = 'block';
    }
    hideAlert();
}

// Form submission
authForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showAlert('Please fill in all required fields', 'error');
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = isLoginMode ? 'Signing In...' : 'Creating Account...';

    try {
        if (isLoginMode) {
            await login(username, password);
        } else {
            const email = document.getElementById('email').value.trim();
            const fullName = document.getElementById('fullName').value.trim();

            if (!email) {
                showAlert('Email is required for registration', 'error');
                submitBtn.disabled = false;
                updateFormMode();
                return;
            }

            await register(username, email, password, fullName);
        }
    } catch (error) {
        console.error('Auth error:', error);
        showAlert(error.message || 'An error occurred. Please try again.', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = isLoginMode ? 'Sign In' : 'Sign Up';
    }
});

// Login function
async function login(username, password) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.detail || 'Login failed');
    }

    // Store tokens
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_expires_at', Date.now() + (data.expires_in * 1000));

    // Show success and redirect
    showAlert('Login successful! Redirecting...', 'success');

    setTimeout(() => {
        window.location.href = 'dashboard.html';
    }, 1000);
}

// Register function
async function register(username, email, password, fullName) {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            email,
            password,
            full_name: fullName || null
        })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || data.detail || 'Registration failed');
    }

    // Show success and switch to login
    showAlert('Account created successfully! Please sign in.', 'success');

    setTimeout(() => {
        isLoginMode = true;
        updateFormMode();
        document.getElementById('username').value = username;
        document.getElementById('password').value = '';
    }, 2000);
}

// Alert functions
function showAlert(message, type) {
    alertBox.textContent = message;
    alertBox.className = `alert alert-${type}`;
    alertBox.style.display = 'block';
}

function hideAlert() {
    alertBox.style.display = 'none';
}

// Token expiration check
function isTokenExpired(token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.exp * 1000 < Date.now();
    } catch (e) {
        return true;
    }
}

// Get auth headers for API requests
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return {};
    }

    return {
        'Authorization': `Bearer ${token}`
    };
}

// Check if user is authenticated
function isAuthenticated() {
    const token = localStorage.getItem('access_token');
    return token && !isTokenExpired(token);
}

// Logout function
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expires_at');
    window.location.href = 'login.html';
}

// Export functions for use in other files
window.authUtils = {
    getAuthHeaders,
    isAuthenticated,
    logout,
    isTokenExpired
};
