// PROSPECTIQ - Results Page JavaScript
// Handles search execution, pagination, and table display

const API_BASE_URL = 'http://localhost:8000';

let currentParams = {};
let currentOffset = 0;
let currentLimit = 50;  // default; server caps by tier
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
        // Build GET query params to avoid CORS preflight
        const params = new URLSearchParams();
        params.set('q', currentParams.keyword || '');
        params.set('offset', String(currentOffset));
        params.set('limit', String(currentLimit));
        params.set('vector_weight', '0.8');
        params.set('lexical_weight', '0.2');
        params.set('ef_search', '64');
        // Always US for now
        params.set('location_country', 'united states');

        // Multi-select arrays as repeated params
        (currentParams.states || []).forEach(st => params.append('regions', st));
        (currentParams.industries || []).forEach(ind => params.append('industries', ind));

        // Experience
        if (currentParams.min_experience) params.set('min_years_experience', String(parseInt(currentParams.min_experience)));
        if (currentParams.max_experience) params.set('max_years_experience', String(parseInt(currentParams.max_experience)));

        // Skills (comma-separated)
        if (currentParams.skills) {
            currentParams.skills.split(',').map(s => s.trim()).filter(Boolean).forEach(skill => params.append('skills', skill));
        }

        // Job Title and Company filters
        if (currentParams.job_title) params.set('job_title', currentParams.job_title);
        if (currentParams.company) params.set('company', currentParams.company);

        // Contact information filters (boolean checkboxes)
        if (currentParams.has_linkedin) params.set('has_linkedin', 'true');
        if (currentParams.has_email) params.set('has_email', 'true');
        if (currentParams.has_phone) params.set('has_phone', 'true');
        if (currentParams.has_website) params.set('has_website', 'true');
        if (currentParams.has_twitter) params.set('has_twitter', 'true');
        if (currentParams.has_github) params.set('has_github', 'true');

        const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || response.statusText);
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
        const skillsArray = profile.skills || [];
        const skillsText = Array.isArray(skillsArray) ? skillsArray.join(', ') : String(skillsArray);
        const skills = skillsText.length > 100
            ? skillsText.substring(0, 100) + '...'
            : skillsText || '—';

        // Truncate summary for display (show first 150 chars)
        const summaryFull = profile.summary || '';
        const summaryDisplay = summaryFull.length > 150
            ? summaryFull.substring(0, 150) + '...'
            : summaryFull || '—';

        // Helper function to create clickable link or dash
        const makeLink = (url, text = 'View') => {
            if (!url || url === '—') return '—';
            return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener" style="color: #60d5ff; text-decoration: none;">${text}</a>`;
        };

        // Format LinkedIn URL (remove 'linkedin.com/in/' prefix for display)
        const linkedinDisplay = profile.linkedin_url ? profile.linkedin_url.replace('linkedin.com/in/', '') : null;

        row.innerHTML = `
            <td>${escapeHtml(profile.first_name || '—')}</td>
            <td>${escapeHtml(profile.last_name || '—')}</td>
            <td>${escapeHtml(profile.job_title || '—')}</td>
            <td>${escapeHtml(profile.company_name || '—')}</td>
            <td>${escapeHtml(profile.industry || '—')}</td>
            <td>${escapeHtml(location)}</td>
            <td>${profile.years_experience !== null ? profile.years_experience + ' yrs' : '—'}</td>
            <td title="${escapeHtml(summaryFull)}" style="max-width: 300px; white-space: normal;">${escapeHtml(summaryDisplay)}</td>
            <td>${profile.linkedin_url ? `<a href="https://${escapeHtml(profile.linkedin_url)}" target="_blank" rel="noopener" style="color: #60d5ff; text-decoration: none;">${escapeHtml(linkedinDisplay)}</a>` : '—'}</td>
            <td>${profile.email ? `<a href="mailto:${escapeHtml(profile.email)}" style="color: #60d5ff; text-decoration: none;">${escapeHtml(profile.email)}</a>` : '—'}</td>
            <td>${profile.phone ? escapeHtml(profile.phone) : '—'}</td>
            <td>${profile.website ? `<a href="https://${escapeHtml(profile.website)}" target="_blank" rel="noopener" style="color: #60d5ff; text-decoration: none;">${escapeHtml(profile.website)}</a>` : '—'}</td>
            <td>${profile.twitter ? makeLink('https://twitter.com/' + profile.twitter, '@' + profile.twitter) : '—'}</td>
            <td>${profile.github ? makeLink('https://github.com/' + profile.github, profile.github) : '—'}</td>
            <td title="${escapeHtml(skillsText)}">${escapeHtml(skills)}</td>
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
    const limitSelect = document.getElementById('limitSelect');

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

    limitSelect.addEventListener('change', async () => {
        currentLimit = parseInt(limitSelect.value);
        currentOffset = 0; // Reset to first page
        await executeSearch();
        updatePaginationState();
        scrollToTop();
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

// === CSV Export ===
async function exportToCSV() {
    try {
        // Build export query
        const params = new URLSearchParams();
        params.set('q', currentParams.keyword || '');
        params.set('limit', '1000');
        params.set('offset', '0');
        params.set('location_country', 'united states');
        (currentParams.states || []).forEach(st => params.append('regions', st));
        (currentParams.industries || []).forEach(ind => params.append('industries', ind));
        if (currentParams.min_experience) params.set('min_years_experience', String(parseInt(currentParams.min_experience)));
        if (currentParams.max_experience) params.set('max_years_experience', String(parseInt(currentParams.max_experience)));
        if (currentParams.skills) {
            currentParams.skills.split(',').map(s => s.trim()).filter(Boolean).forEach(skill => params.append('skills', skill));
        }

        const resp = await fetch(`${API_BASE_URL}/export/csv?${params.toString()}`);
        if (!resp.ok) throw new Error('Failed to export CSV');

        const blob = await resp.blob();
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `prospectiq_results_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export CSV: ' + error.message);
    }
}

function convertToCSV(results) {
    if (results.length === 0) return '';

    // Define CSV headers
    const headers = [
        'Full Name',
        'Job Title',
        'Company',
        'Industry',
        'Location',
        'Country',
        'Region',
        'City',
        'Years Experience',
        'LinkedIn URL',
        'Email',
        'Phone',
        'Website',
        'Twitter',
        'GitHub',
        'Skills',
        'Headline',
        'Summary'
    ];

    // Escape CSV field (handle quotes and commas)
    const escapeCSV = (field) => {
        if (field === null || field === undefined) return '';
        const str = String(field);
        if (str.includes('"') || str.includes(',') || str.includes('\n')) {
            return '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    };

    // Build CSV rows
    const rows = results.map(profile => [
        profile.full_name || '',
        profile.job_title || '',
        profile.company_name || '',
        profile.industry || '',
        profile.location || '',
        profile.location_country || '',
        profile.region || '',
        profile.locality || '',
        profile.years_experience !== null ? profile.years_experience : '',
        profile.linkedin_url || '',
        profile.email || '',
        profile.phone || '',
        profile.website || '',
        profile.twitter || '',
        profile.github || '',
        Array.isArray(profile.skills) ? profile.skills.join('; ') : '',
        profile.headline || '',
        profile.summary || ''
    ].map(escapeCSV).join(','));

    // Combine headers and rows
    return [headers.join(','), ...rows].join('\n');
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
