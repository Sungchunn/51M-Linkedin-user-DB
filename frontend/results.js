// INSIGHT - Results Page JavaScript
// Handles search execution, pagination, and table display

const API_BASE_URL = 'http://localhost:8000';

let currentParams = {};
let currentOffset = 0;
let currentLimit = 50;
let totalCount = 0;

// === Initialize Page ===
document.addEventListener('DOMContentLoaded', async () => {
    // Get search params from sessionStorage
    const paramsStr = sessionStorage.getItem('searchParams');

    if (!paramsStr) {
        // No search params - redirect to search page
        window.location.href = 'index.html';
        return;
    }

    currentParams = JSON.parse(paramsStr);
    currentOffset = currentParams.offset || 0;
    currentLimit = currentParams.limit || 50;

    // Execute search
    await executeSearch();

    // Setup pagination
    setupPagination();
});

// === Execute Search ===
async function executeSearch() {
    const loadingState = document.getElementById('loadingState');
    const emptyState = document.getElementById('emptyState');
    const errorState = document.getElementById('errorState');
    const resultsTable = document.getElementById('resultsTable');
    const resultsSummary = document.getElementById('resultsSummary');

    // Show loading
    loadingState.style.display = 'block';
    emptyState.style.display = 'none';
    errorState.style.display = 'none';
    resultsTable.style.display = 'none';
    resultsSummary.style.display = 'none';

    try {
        // Build query string
        const params = new URLSearchParams({
            ...currentParams,
            offset: currentOffset,
            limit: currentLimit
        });

        // Execute search
        const response = await fetch(`${API_BASE_URL}/search?${params}`);

        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
        }

        const data = await response.json();
        totalCount = data.total_count;

        // Hide loading
        loadingState.style.display = 'none';

        if (data.returned_count === 0) {
            // Show empty state
            emptyState.style.display = 'block';
        } else {
            // Show results
            displayResults(data);
            displaySummary(data);
            resultsTable.style.display = 'table';
            resultsSummary.style.display = 'block';
        }

    } catch (error) {
        console.error('Search error:', error);

        // Show error state
        loadingState.style.display = 'none';
        errorState.style.display = 'block';
        document.getElementById('errorMessage').textContent = error.message;
    }
}

// === Display Results ===
function displayResults(data) {
    const tbody = document.getElementById('resultsBody');
    tbody.innerHTML = '';

    data.results.forEach(profile => {
        const row = document.createElement('tr');

        // Format location
        const location = [
            profile.locality,
            profile.region,
            profile.location_country
        ].filter(Boolean).join(', ') || '—';

        // Truncate skills if too long
        const skills = profile.skills
            ? (profile.skills.length > 100
                ? profile.skills.substring(0, 100) + '...'
                : profile.skills)
            : '—';

        row.innerHTML = `
            <td><strong>${escapeHtml(profile.full_name || '—')}</strong></td>
            <td>${escapeHtml(profile.job_title || '—')}</td>
            <td>${escapeHtml(profile.company_name || '—')}</td>
            <td>${escapeHtml(profile.industry || '—')}</td>
            <td>${escapeHtml(location)}</td>
            <td>${profile.years_experience !== null ? profile.years_experience + ' yrs' : '—'}</td>
            <td title="${escapeHtml(profile.skills || '')}">${escapeHtml(skills)}</td>
        `;

        tbody.appendChild(row);
    });
}

// === Display Summary ===
function displaySummary(data) {
    const resultsCount = document.getElementById('resultsCount');
    const queryTime = document.getElementById('queryTime');
    const filtersApplied = document.getElementById('filtersApplied');

    // Results count
    const start = currentOffset + 1;
    const end = Math.min(currentOffset + data.returned_count, totalCount);
    resultsCount.textContent = `Showing ${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(totalCount)} results`;

    // Query time
    queryTime.textContent = `Query time: ${data.query_time_ms.toFixed(0)}ms`;
    queryTime.className = data.query_time_ms < 1000 ? 'text-success' : 'text-muted';

    // Filters applied
    filtersApplied.innerHTML = '';

    if (Object.keys(data.filters_applied).length === 0) {
        filtersApplied.innerHTML = '<span class="filter-tag">No filters applied</span>';
    } else {
        Object.entries(data.filters_applied).forEach(([key, value]) => {
            const tag = document.createElement('span');
            tag.className = 'filter-tag';
            tag.textContent = `${formatFilterKey(key)}: ${value}`;
            filtersApplied.appendChild(tag);
        });
    }
}

// === Setup Pagination ===
function setupPagination() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');

    prevBtn.addEventListener('click', async () => {
        if (currentOffset > 0) {
            currentOffset = Math.max(0, currentOffset - currentLimit);
            await executeSearch();
            updatePaginationState();
            scrollToTop();
        }
    });

    nextBtn.addEventListener('click', async () => {
        if (currentOffset + currentLimit < totalCount) {
            currentOffset += currentLimit;
            await executeSearch();
            updatePaginationState();
            scrollToTop();
        }
    });

    updatePaginationState();
}

function updatePaginationState() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');

    // Update button states
    prevBtn.disabled = currentOffset === 0;
    nextBtn.disabled = currentOffset + currentLimit >= totalCount;

    // Update page info
    const currentPage = Math.floor(currentOffset / currentLimit) + 1;
    const totalPages = Math.ceil(totalCount / currentLimit);
    pageInfo.textContent = `Page ${currentPage} of ${formatNumber(totalPages)}`;
}

// === Navigation ===
function goBack() {
    window.history.back();
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// === Utility Functions ===
function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

function formatFilterKey(key) {
    const keyMap = {
        keyword: 'Keyword',
        country: 'Country',
        industry: 'Industry',
        min_experience: 'Min Experience',
        max_experience: 'Max Experience',
        skills: 'Skills'
    };
    return keyMap[key] || key;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
