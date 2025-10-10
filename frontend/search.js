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
        // Load countries
        const countriesRes = await fetch(`${API_BASE_URL}/countries`);
        const countriesData = await countriesRes.json();

        const countrySelect = document.getElementById('country');
        countriesData.countries.forEach(country => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        });

        // Load industries
        const industriesRes = await fetch(`${API_BASE_URL}/industries`);
        const industriesData = await industriesRes.json();

        const industrySelect = document.getElementById('industry');
        industriesData.industries.forEach(industry => {
            const option = document.createElement('option');
            option.value = industry;
            option.textContent = industry;
            industrySelect.appendChild(option);
        });

    } catch (error) {
        console.error('Failed to load filters:', error);
    }
}

// === Load Dataset Stats ===
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
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
