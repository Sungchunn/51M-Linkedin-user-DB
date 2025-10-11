// INSIGHT - Search Page JavaScript
// Handles search form, filter loading, and stats

const API_BASE_URL = 'http://localhost:8000';

// === Initialize Page ===
document.addEventListener('DOMContentLoaded', async () => {
    await loadFilters();
    await loadStats();
    setupFormHandler();
});

// === Load Filter Options ===
async function loadFilters() {
    try {
        // Show loading message
        const countrySelect = document.getElementById('country');
        const industrySelect = document.getElementById('industry');

        countrySelect.innerHTML = '<option value="">Loading countries...</option>';
        industrySelect.innerHTML = '<option value="">Loading industries...</option>';

        // Load countries with timeout
        const countriesRes = await fetchWithTimeout(`${API_BASE_URL}/countries`, 30000);
        const countriesData = await countriesRes.json();

        countrySelect.innerHTML = '<option value="">All Countries</option>';
        countriesData.countries.forEach(country => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        });

        // Load industries with timeout
        const industriesRes = await fetchWithTimeout(`${API_BASE_URL}/industries`, 30000);
        const industriesData = await industriesRes.json();

        industrySelect.innerHTML = '<option value="">All Industries</option>';
        industriesData.industries.forEach(industry => {
            const option = document.createElement('option');
            option.value = industry;
            option.textContent = industry;
            industrySelect.appendChild(option);
        });

    } catch (error) {
        console.error('Failed to load filters:', error);
        document.getElementById('country').innerHTML = '<option value="">Error loading countries</option>';
        document.getElementById('industry').innerHTML = '<option value="">Error loading industries</option>';

        // Show user-friendly error
        const statsSection = document.getElementById('statsSection');
        statsSection.innerHTML = `
            <div style="padding: 20px; background: #fee2e2; border-radius: 8px; color: #991b1b;">
                <strong>⚠️ Cannot connect to API</strong>
                <p style="margin-top: 8px;">Make sure the API server is running:</p>
                <code style="background: white; padding: 4px 8px; border-radius: 4px; display: block; margin-top: 8px;">
                    ./start_duckdb_api.sh
                </code>
            </div>
        `;
    }
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

// === Setup Form Handler ===
function setupFormHandler() {
    const form = document.getElementById('searchForm');
    const searchBtn = document.getElementById('searchBtn');
    const btnText = document.getElementById('btnText');
    const btnLoading = document.getElementById('btnLoading');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Show loading state
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';
        searchBtn.disabled = true;

        // Build query parameters
        const formData = new FormData(form);
        const params = {};

        for (let [key, value] of formData.entries()) {
            if (value.trim() !== '') {
                params[key] = value;
            }
        }

        // Add offset and limit
        params.offset = 0;
        params.limit = 50;

        // Store search params in sessionStorage
        sessionStorage.setItem('searchParams', JSON.stringify(params));

        // Navigate to results page
        window.location.href = 'results.html';
    });
}

// === Utility Functions ===
function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}
