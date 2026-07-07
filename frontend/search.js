// PROSPECTIQ - Search Page JavaScript
// Handles search form, filter loading, and stats

// API Base URL is now loaded from config.js
const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8000';

// === Initialize Page ===
document.addEventListener('DOMContentLoaded', async () => {
    // Reset button state (in case user navigated back)
    resetButtonState();

    // Always setup form handler first (don't depend on API)
    setupFormHandler();

    // Load filters and stats (non-blocking)
    try {
        await loadFilters();
    } catch (error) {
        console.error('Failed to load filters:', error);
    }

    try {
        await loadStats();
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
});

// === Handle pageshow event (back/forward cache) ===
window.addEventListener('pageshow', (event) => {
    // If page was loaded from bfcache (back/forward navigation)
    if (event.persisted) {
        console.log('Page restored from bfcache - resetting button state');
        resetButtonState();
    }
});

// Global lists
let allIndustries = [];
let allStates = [];

// === Load Filter Options ===
async function loadFilters() {
    try {
        // Show loading message
        const statesContainer = document.getElementById('statesContainer');
        const industryContainer = document.getElementById('industryContainer');

        statesContainer.innerHTML = '<p style="color: var(--text-muted); padding: 8px;">Loading states...</p>';
        industryContainer.innerHTML = '<p style="color: var(--text-muted); padding: 8px;">Loading industries...</p>';

        // Load states and industries in parallel
        const regionsUrl = `${API_BASE_URL}/regions?country=${encodeURIComponent('united states')}`;
        const [statesRes, industriesRes] = await Promise.all([
            fetchWithTimeout(regionsUrl, 30000),
            fetchWithTimeout(`${API_BASE_URL}/industries`, 30000)
        ]);

        if (!statesRes.ok) {
            const text = await statesRes.text().catch(() => '');
            throw new Error(`States fetch failed (${statesRes.status}): ${text}`);
        }
        if (!industriesRes.ok) {
            const text = await industriesRes.text().catch(() => '');
            throw new Error(`Industries fetch failed (${industriesRes.status}): ${text}`);
        }

        const statesData = await statesRes.json();
        const industriesData = await industriesRes.json();

        allStates = statesData.regions.map(r => r.region);
        allIndustries = industriesData.industries;

        // Render states checkboxes
        renderCheckboxes('statesContainer', allStates);

        // Setup states search
        const statesSearch = document.getElementById('statesSearch');
        statesSearch.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const filtered = allStates.filter(state =>
                state.toLowerCase().includes(searchTerm)
            );
            renderCheckboxes('statesContainer', filtered);
        });

        // Render industry checkboxes
        renderCheckboxes('industryContainer', allIndustries);

        // Setup industry search
        const industrySearch = document.getElementById('industrySearch');
        industrySearch.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const filtered = allIndustries.filter(ind =>
                ind.toLowerCase().includes(searchTerm)
            );
            renderCheckboxes('industryContainer', filtered);
        });

    } catch (error) {
        console.error('Failed to load filters:', error);
        document.getElementById('statesContainer').innerHTML = '<p style="color: var(--error); padding: 8px;">Error loading states</p>';
        document.getElementById('industryContainer').innerHTML = '<p style="color: var(--error); padding: 8px;">Error loading industries</p>';

        // Show user-friendly error
        const statsSection = document.getElementById('statsSection');
        if (statsSection) {
            statsSection.innerHTML = `
                <div style="padding: 20px; background: var(--surface); border: 1px solid var(--error); border-radius: 8px; color: var(--error);">
                    <strong>⚠️ Cannot connect to API</strong>
                    <p style="margin-top: 8px;">Make sure the API server is running:</p>
                    <code style="background: var(--background); padding: 4px 8px; border-radius: 4px; display: block; margin-top: 8px; color: var(--text-primary);">
                        ./start_api.sh
                    </code>
                </div>
            `;
        }
    }
}

// === Render Checkboxes (Generic) ===
function renderCheckboxes(containerId, items) {
    const container = document.getElementById(containerId);
    const currentSelected = getSelectedValues(containerId);

    container.innerHTML = '';

    if (items.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); padding: 8px;">No items found</p>';
        return;
    }

    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'industry-checkbox';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `${containerId}_${item.replace(/\s+/g, '_')}`;
        checkbox.value = item;
        checkbox.checked = currentSelected.includes(item);

        // Add change listener to update count
        checkbox.addEventListener('change', () => updateFilterCount(containerId));

        const label = document.createElement('label');
        label.htmlFor = checkbox.id;
        label.textContent = item;

        div.appendChild(checkbox);
        div.appendChild(label);
        container.appendChild(div);
    });

    // Update count after rendering
    updateFilterCount(containerId);
}

// === Get Selected Values (Generic) ===
function getSelectedValues(containerId) {
    const checkboxes = document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`);
    return Array.from(checkboxes).map(cb => cb.value);
}

// === Update Filter Count ===
function updateFilterCount(containerId) {
    const selectedCount = getSelectedValues(containerId).length;

    // Determine which count element to update
    let countElement;
    if (containerId === 'statesContainer') {
        countElement = document.getElementById('statesCount');
    } else if (containerId === 'industryContainer') {
        countElement = document.getElementById('industryCount');
    }

    if (countElement) {
        if (selectedCount > 0) {
            countElement.textContent = `${selectedCount} selected`;
            countElement.style.display = 'inline-block';
        } else {
            countElement.style.display = 'none';
        }
    }
}

// === Get Selected Industries ===
function getSelectedIndustries() {
    return getSelectedValues('industryContainer');
}

// === Get Selected States ===
function getSelectedStates() {
    return getSelectedValues('statesContainer');
}

// Fetch with timeout helper
async function fetchWithTimeout(url, timeout = 30000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(id);
        return response;
    } catch (error) {
        clearTimeout(id);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out - API may be processing large dataset');
        }
        throw error;
    }
}

// === Load Dataset Stats ===
async function loadStats() {
    const statsSection = document.getElementById('statsSection');

    // Show loading state
    statsSection.innerHTML = `
        <div style="padding: 20px; text-align: center; color: var(--text-secondary);">
            <div class="spinner" style="margin: 0 auto 16px;"></div>
            <p>Loading dataset statistics...</p>
            <small>(This may take 10-15 minutes for DuckDB + S3)</small>
        </div>
    `;

    try {
        const response = await fetchWithTimeout(`${API_BASE_URL}/stats`, 900000); // 15 min timeout
        const data = await response.json();

        const statsSection = document.getElementById('statsSection');
        statsSection.innerHTML = `
            <h3 style="margin-bottom: 20px; color: var(--text-primary);">📊 Dataset Statistics</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${formatNumber(data.total_profiles)}</div>
                    <div class="stat-label">Total Profiles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${formatNumber(data.countries.length)}</div>
                    <div class="stat-label">Countries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${formatNumber(data.industries.length)}</div>
                    <div class="stat-label">Industries</div>
                </div>
            </div>
            <div style="margin-top: 24px;">
                <h4 style="margin-bottom: 12px; color: var(--text-secondary);">Top Countries</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    ${data.countries.slice(0, 10).map(c =>
                        `<span class="filter-tag">${c.country} (${formatNumber(c.count)})</span>`
                    ).join('')}
                </div>
            </div>
            <div style="margin-top: 24px;">
                <h4 style="margin-bottom: 12px; color: var(--text-secondary);">Top Industries</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    ${data.industries.slice(0, 10).map(i =>
                        `<span class="filter-tag">${i.industry} (${formatNumber(i.count)})</span>`
                    ).join('')}
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load stats:', error);
        statsSection.innerHTML = `
            <div style="padding: 20px; background: #fef3c7; border-radius: 8px; color: #92400e;">
                <strong>⚠️ Stats Loading Timed Out</strong>
                <p style="margin-top: 8px;">
                    DuckDB is downloading 15GB from S3 (takes 10-15 minutes).
                    You can still search without stats, or wait for them to load.
                </p>
                <button onclick="location.reload()" style="margin-top: 12px; padding: 8px 16px; background: white; border: 1px solid #d97706; border-radius: 6px; cursor: pointer;">
                    Retry
                </button>
            </div>
        `;
    }
}

// === Reset Button State ===
function resetButtonState() {
    const searchBtn = document.getElementById('searchBtn');
    const btnText = document.getElementById('btnText');
    const btnLoading = document.getElementById('btnLoading');

    if (searchBtn && btnText && btnLoading) {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        searchBtn.disabled = false;
    }
}

// === Setup Form Handler ===
function setupFormHandler() {
    const form = document.getElementById('searchForm');
    const searchBtn = document.getElementById('searchBtn');
    const btnText = document.getElementById('btnText');
    const btnLoading = document.getElementById('btnLoading');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        console.log('Form submitted!');

        // Show loading state
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';
        searchBtn.disabled = true;

        try {
            // Build query parameters
            const formData = new FormData(form);
            const params = {};

            for (let [key, value] of formData.entries()) {
                if (value && value.trim() !== '') {
                    params[key] = value.trim();
                }
            }

            // Get selected industries (multi-select)
            const selectedIndustries = getSelectedIndustries();
            if (selectedIndustries.length > 0) {
                params.industries = selectedIndustries;  // Array
            }

            // Get selected US states (multi-select)
            const selectedStates = getSelectedStates();
            if (selectedStates.length > 0) {
                params.states = selectedStates;  // Array
            }

            // Collect contact information checkboxes
            if (document.getElementById('has_linkedin')?.checked) {
                params.has_linkedin = true;
            }
            if (document.getElementById('has_email')?.checked) {
                params.has_email = true;
            }
            if (document.getElementById('has_phone')?.checked) {
                params.has_phone = true;
            }
            if (document.getElementById('has_website')?.checked) {
                params.has_website = true;
            }
            if (document.getElementById('has_twitter')?.checked) {
                params.has_twitter = true;
            }
            if (document.getElementById('has_github')?.checked) {
                params.has_github = true;
            }

            // Add offset and limit
            params.offset = 0;
            params.limit = 100;  // API max is 100

            console.log('Search params:', params);

            // Store search params in sessionStorage
            sessionStorage.setItem('searchParams', JSON.stringify(params));
            console.log('Stored in sessionStorage:', sessionStorage.getItem('searchParams'));

            // Navigate to results page
            console.log('Navigating to results.html...');
            window.location.href = 'results.html';
        } catch (error) {
            console.error('Form submission error:', error);
            // Reset button state on error
            resetButtonState();
            alert('Error: ' + error.message);
        }
    });
}

// === Utility Functions ===
function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}
