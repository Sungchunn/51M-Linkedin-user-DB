// PROSPECTIQ - API Keys JavaScript
// Handles API key management

const API_BASE_URL = 'http://localhost:8000';

// Check authentication on load
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.authUtils.isAuthenticated()) {
        window.location.href = 'login.html';
        return;
    }

    // Load user profile and API keys in parallel for faster loading
    await Promise.all([
        loadUserProfile(),
        loadApiKeys()
    ]);
});

// Load user profile
async function loadUserProfile() {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            headers: window.authUtils.getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to load profile');
        }

        const user = await response.json();
        document.getElementById('username').textContent = user.username;
    } catch (error) {
        console.error('Error loading profile:', error);
        window.authUtils.logout();
    }
}

// Load API keys
async function loadApiKeys() {
    const container = document.getElementById('apiKeysList');
    container.innerHTML = '<div class="empty-state">Loading API keys...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/auth/api-keys`, {
            headers: window.authUtils.getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to load API keys');
        }

        const keys = await response.json();
        renderApiKeys(keys);
    } catch (error) {
        console.error('Error loading API keys:', error);
        container.innerHTML = `
            <div class="empty-state" style="color: var(--error);">
                ⚠️ Error loading API keys. Please refresh the page.
            </div>
        `;
    }
}

// Render API keys
function renderApiKeys(keys) {
    const container = document.getElementById('apiKeysList');

    if (keys.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                No API keys yet. Create your first key to get started!
            </div>
        `;
        return;
    }

    container.innerHTML = keys.map(key => `
        <div class="api-key-card">
            <div class="api-key-info">
                <div class="api-key-name">${escapeHtml(key.key_name)}</div>
                <div class="api-key-details">
                    <span class="api-key-prefix">${key.key_prefix}...</span>
                    <span>•</span>
                    <span>Tier: ${key.tier}</span>
                    <span>•</span>
                    <span>Uses: ${key.usage_count}</span>
                    ${key.last_used_at ? `<span>•</span><span>Last used: ${formatDate(key.last_used_at)}</span>` : ''}
                </div>
                <div class="api-key-scopes">
                    ${key.scopes.map(scope => `<span class="scope-badge">${scope}</span>`).join('')}
                </div>
            </div>
            <div class="api-key-actions">
                <button class="btn-revoke" onclick="revokeApiKey('${key.id}', '${escapeHtml(key.key_name)}')">
                    Revoke
                </button>
            </div>
        </div>
    `).join('');
}

// Open create key modal
function openCreateKeyModal() {
    document.getElementById('createKeyModal').style.display = 'flex';
    document.getElementById('keyCreatedBox').style.display = 'none';
    document.getElementById('createKeyForm').reset();
    document.querySelector('input[value="search:read"]').checked = true;
}

// Close create key modal
function closeCreateKeyModal() {
    document.getElementById('createKeyModal').style.display = 'none';
}

// Create API key form submission
document.getElementById('createKeyForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const keyName = document.getElementById('keyName').value.trim();
    const tier = document.getElementById('tier').value;
    const scopeCheckboxes = document.querySelectorAll('input[name="scope"]:checked');
    const scopes = Array.from(scopeCheckboxes).map(cb => cb.value);

    if (scopes.length === 0) {
        alert('Please select at least one scope');
        return;
    }

    const createBtn = document.getElementById('createKeyBtn');
    createBtn.disabled = true;
    createBtn.textContent = 'Creating...';

    try {
        const response = await fetch(`${API_BASE_URL}/auth/api-keys`, {
            method: 'POST',
            headers: {
                ...window.authUtils.getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                key_name: keyName,
                scopes: scopes,
                tier: tier
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.detail || 'Failed to create API key');
        }

        const newKey = await response.json();

        // Show the created key
        document.getElementById('createdKeyValue').textContent = newKey.api_key;
        document.getElementById('keyCreatedBox').style.display = 'block';

        // Hide form elements
        document.querySelectorAll('.form-group').forEach(el => el.style.display = 'none');
        document.getElementById('createKeyBtn').style.display = 'none';

        // Reload the keys list
        await loadApiKeys();
    } catch (error) {
        console.error('Error creating API key:', error);
        alert(error.message);
        createBtn.disabled = false;
        createBtn.textContent = 'Create Key';
    }
});

// Copy API key to clipboard
function copyApiKey() {
    const keyValue = document.getElementById('createdKeyValue').textContent;
    navigator.clipboard.writeText(keyValue).then(() => {
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.background = 'rgba(0, 255, 157, 0.2)';

        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
    });
}

// Revoke API key
async function revokeApiKey(keyId, keyName) {
    if (!confirm(`Are you sure you want to revoke "${keyName}"? This action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/api-keys/${keyId}`, {
            method: 'DELETE',
            headers: window.authUtils.getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to revoke API key');
        }

        // Reload the keys list
        await loadApiKeys();
    } catch (error) {
        console.error('Error revoking API key:', error);
        alert('Failed to revoke API key. Please try again.');
    }
}

// Logout
function logout() {
    window.authUtils.logout();
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
        return `${diffMins} min ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// Close modal when clicking outside
document.getElementById('createKeyModal').addEventListener('click', (e) => {
    if (e.target.id === 'createKeyModal') {
        closeCreateKeyModal();
    }
});
