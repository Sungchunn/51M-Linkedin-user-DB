# PROSPECTIQ API Design Proposal
## Comprehensive API Architecture for Frontend-Backend Stability

**Status:** Proposal (Not Yet Implemented)
**Date:** 2025-10-21
**Goal:** Design a robust API layer that won't break when we make updates

---

## Executive Summary

### Current Problem
When we previously touched API updates, the frontend broke because:
1. **Inconsistent parameter names** between frontend and backend
2. **No API versioning** - changes break existing clients
3. **Implicit contracts** - unclear what fields are required vs optional
4. **Mixed GET/POST patterns** - confusion on which to use when
5. **No request/response validation on frontend** - silent failures
6. **Hardcoded API URLs** - scattered across multiple files

### Proposed Solution
A **comprehensive API design** with:
1. **Strict versioning** (`/v1/`, `/v2/`)
2. **Explicit contracts** (OpenAPI/Swagger spec)
3. **Client SDK** (generated from spec)
4. **Centralized API client** (single source of truth)
5. **Backward compatibility guarantees**
6. **Comprehensive error handling**

---

## 1. API Versioning Strategy

### Current State (No Versioning)
```
GET  /search
POST /search
GET  /regions
GET  /industries
```

**Problem:** Any change to `/search` breaks all existing clients.

### Proposed: URL-Based Versioning

```
# Version 1 (Current, Stable)
GET  /v1/search
POST /v1/search
GET  /v1/filters/regions
GET  /v1/filters/industries
GET  /v1/filters/countries
GET  /v1/export/csv
GET  /v1/export/ndjson

# Version 2 (Future, Breaking Changes)
POST /v2/search          # Different request schema
GET  /v2/profiles/{id}   # New endpoint
```

### Versioning Rules

1. **v1 is forever stable** - Never break existing v1 endpoints
2. **New features go to latest version** - Add to v2, v3, etc.
3. **Deprecation timeline** - 6 months notice before removing old versions
4. **Version in Accept header** (alternative):
   ```
   Accept: application/vnd.prospectiq.v1+json
   ```

### Migration Path
```javascript
// Old (breaks easily)
fetch('http://localhost:8000/search')

// New (explicit version)
fetch('http://localhost:8000/v1/search')

// Future-proof (client library handles versioning)
apiClient.search.query(params)
```

---

## 2. Request/Response Contracts

### Problem: Frontend-Backend Parameter Mismatch

**Current Frontend (search.js:332)**
```javascript
params.states = selectedStates;  // 'states' key
```

**Current Backend (app.py:531)**
```python
regions: list[str] | None = Query(None)  # expects 'regions' key
```

**Result:** States filter silently fails! 🐛

### Solution: Strict Contract Definition

#### A. OpenAPI 3.0 Specification

Create `backend/api/openapi.yaml`:

```yaml
openapi: 3.0.0
info:
  title: PROSPECTIQ API
  version: 1.0.0
  description: Semantic talent search API

paths:
  /v1/search:
    get:
      operationId: searchProfiles
      summary: Search for talent profiles
      parameters:
        - name: q
          in: query
          description: Search query text
          required: false
          schema:
            type: string
            example: "senior software engineer"

        - name: regions
          in: query
          description: US states/regions (multi-select)
          required: false
          schema:
            type: array
            items:
              type: string
          explode: true  # ?regions=CA&regions=NY
          example: ["California", "New York"]

        - name: industries
          in: query
          description: Industries (multi-select)
          required: false
          schema:
            type: array
            items:
              type: string
          explode: true
          example: ["Technology", "Finance"]

        - name: limit
          in: query
          required: false
          schema:
            type: integer
            minimum: 1
            maximum: 1000
            default: 20

        - name: offset
          in: query
          required: false
          schema:
            type: integer
            minimum: 0
            default: 0

      responses:
        '200':
          description: Search results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'
        '400':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

components:
  schemas:
    SearchResponse:
      type: object
      required:
        - results
        - total_count
        - returned_count
        - query_time_ms
      properties:
        results:
          type: array
          items:
            $ref: '#/components/schemas/Profile'
        total_count:
          type: integer
          minimum: 0
        returned_count:
          type: integer
          minimum: 0
        offset:
          type: integer
        limit:
          type: integer
        query_time_ms:
          type: number
          format: float
        filters_applied:
          type: object

    Profile:
      type: object
      required:
        - id
        - full_name
        - score
      properties:
        id:
          type: string
          format: uuid
        full_name:
          type: string
        first_name:
          type: string
          nullable: true
        last_name:
          type: string
          nullable: true
        job_title:
          type: string
          nullable: true
        company_name:
          type: string
          nullable: true
        industry:
          type: string
          nullable: true
        location_country:
          type: string
          nullable: true
        region:
          type: string
          nullable: true
        locality:
          type: string
          nullable: true
        years_experience:
          type: integer
          nullable: true
          minimum: 0
          maximum: 80
        skills:
          type: array
          items:
            type: string
          nullable: true
        linkedin_url:
          type: string
          format: uri
          nullable: true
        email:
          type: string
          format: email
          nullable: true
        phone:
          type: string
          nullable: true
        score:
          type: number
          format: float
          minimum: 0.0
          maximum: 1.0

    ErrorResponse:
      type: object
      required:
        - error
        - timestamp
      properties:
        error:
          type: string
        detail:
          type: string
          nullable: true
        timestamp:
          type: string
          format: date-time
```

#### B. Auto-Generate TypeScript/JavaScript Types

Use `openapi-typescript` to generate types:

```bash
npm install -D openapi-typescript
npx openapi-typescript backend/api/openapi.yaml -o frontend/api-types.ts
```

**Generated `frontend/api-types.ts`:**
```typescript
export interface SearchRequest {
  q?: string;
  regions?: string[];
  industries?: string[];
  limit?: number;
  offset?: number;
  min_years_experience?: number;
  max_years_experience?: number;
  skills?: string[];
}

export interface SearchResponse {
  results: Profile[];
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  query_time_ms: number;
  filters_applied: Record<string, any>;
}

export interface Profile {
  id: string;
  full_name: string;
  first_name: string | null;
  last_name: string | null;
  job_title: string | null;
  company_name: string | null;
  industry: string | null;
  region: string | null;
  locality: string | null;
  years_experience: number | null;
  skills: string[] | null;
  linkedin_url: string | null;
  email: string | null;
  phone: string | null;
  score: number;
}
```

---

## 3. Centralized API Client

### Problem: Scattered API Calls

**Current State:**
```javascript
// search.js:53
fetch(`${API_BASE_URL}/regions?country=...`)

// results.js:73
fetch(`${API_BASE_URL}/search?${params}`)

// results.js:273
fetch(`${API_BASE_URL}/export/csv?${params}`)

// dashboard.js:45
fetch(`${API_BASE_URL}/auth/api-keys`)
```

**Problems:**
- Hardcoded URLs in 4+ files
- No centralized error handling
- No request/response validation
- No retry logic
- No loading states management

### Solution: API Client Library

Create `frontend/api-client.js`:

```javascript
/**
 * PROSPECTIQ API Client
 * Single source of truth for all API interactions
 *
 * Features:
 * - Automatic retries
 * - Request/response validation
 * - Error handling
 * - Loading state management
 * - Type safety (with TypeScript)
 */

class ProspectIQClient {
  constructor(config = {}) {
    this.baseURL = config.baseURL || 'http://localhost:8000';
    this.version = config.version || 'v1';
    this.apiKey = config.apiKey || null;
    this.timeout = config.timeout || 30000;
    this.retries = config.retries || 3;
  }

  /**
   * Build full API URL
   */
  buildURL(endpoint) {
    return `${this.baseURL}/${this.version}/${endpoint}`;
  }

  /**
   * Get default headers
   */
  getHeaders() {
    const headers = {
      'Content-Type': 'application/json',
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    return headers;
  }

  /**
   * Fetch with timeout and retries
   */
  async fetchWithRetry(url, options, retriesLeft = this.retries) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Retry on 5xx errors
      if (response.status >= 500 && retriesLeft > 0) {
        console.warn(`Server error (${response.status}), retrying... (${retriesLeft} left)`);
        await this.sleep(1000 * (this.retries - retriesLeft + 1)); // Exponential backoff
        return this.fetchWithRetry(url, options, retriesLeft - 1);
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error.name === 'AbortError') {
        if (retriesLeft > 0) {
          console.warn('Request timeout, retrying...', retriesLeft);
          return this.fetchWithRetry(url, options, retriesLeft - 1);
        }
        throw new APIError('Request timeout', 'TIMEOUT');
      }

      throw error;
    }
  }

  /**
   * Sleep helper for retries
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Make API request
   */
  async request(endpoint, options = {}) {
    const url = this.buildURL(endpoint);
    const response = await this.fetchWithRetry(url, {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...options.headers,
      },
    });

    // Parse response
    const contentType = response.headers.get('content-type');
    let data;

    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    // Handle errors
    if (!response.ok) {
      throw new APIError(
        data.error || data.detail || response.statusText,
        response.status,
        data
      );
    }

    return data;
  }

  // ==================== SEARCH API ====================

  /**
   * Search profiles
   * @param {SearchRequest} params - Search parameters
   * @returns {Promise<SearchResponse>}
   */
  async search(params) {
    // Validate params (basic)
    if (params.limit && (params.limit < 1 || params.limit > 1000)) {
      throw new APIError('Limit must be between 1 and 1000', 'VALIDATION_ERROR');
    }

    // Build query string
    const query = new URLSearchParams();

    if (params.q) query.set('q', params.q);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    if (params.location_country) query.set('location_country', params.location_country);

    // Multi-select arrays
    (params.regions || []).forEach(r => query.append('regions', r));
    (params.industries || []).forEach(i => query.append('industries', i));
    (params.skills || []).forEach(s => query.append('skills', s));

    // Experience
    if (params.min_years_experience !== undefined) {
      query.set('min_years_experience', String(params.min_years_experience));
    }
    if (params.max_years_experience !== undefined) {
      query.set('max_years_experience', String(params.max_years_experience));
    }

    return this.request(`search?${query.toString()}`);
  }

  /**
   * Export search results to CSV
   */
  async exportCSV(params) {
    const query = this.buildSearchQuery(params);
    const url = this.buildURL(`export/csv?${query}`);

    const response = await fetch(url, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new APIError('Export failed', response.status);
    }

    return response.blob();
  }

  /**
   * Export search results to NDJSON
   */
  async exportNDJSON(params) {
    const query = this.buildSearchQuery(params);
    const url = this.buildURL(`export/ndjson?${query}`);

    const response = await fetch(url, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new APIError('Export failed', response.status);
    }

    return response.text();
  }

  /**
   * Build search query string (helper)
   */
  buildSearchQuery(params) {
    const query = new URLSearchParams();

    if (params.q) query.set('q', params.q);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    if (params.location_country) query.set('location_country', params.location_country);

    (params.regions || []).forEach(r => query.append('regions', r));
    (params.industries || []).forEach(i => query.append('industries', i));
    (params.skills || []).forEach(s => query.append('skills', s));

    if (params.min_years_experience !== undefined) {
      query.set('min_years_experience', String(params.min_years_experience));
    }
    if (params.max_years_experience !== undefined) {
      query.set('max_years_experience', String(params.max_years_experience));
    }

    return query.toString();
  }

  // ==================== FILTERS API ====================

  /**
   * Get list of countries
   */
  async getCountries() {
    return this.request('filters/countries');
  }

  /**
   * Get list of regions/states
   * @param {string} country - Optional country filter
   */
  async getRegions(country = null) {
    const query = country ? `?country=${encodeURIComponent(country)}` : '';
    return this.request(`filters/regions${query}`);
  }

  /**
   * Get list of industries
   */
  async getIndustries() {
    return this.request('filters/industries');
  }

  /**
   * Get list of localities/cities
   */
  async getLocalities(country = null, region = null) {
    const params = new URLSearchParams();
    if (country) params.set('country', country);
    if (region) params.set('region', region);
    const query = params.toString() ? `?${params}` : '';
    return this.request(`filters/localities${query}`);
  }

  // ==================== STATS API ====================

  /**
   * Get dataset statistics
   */
  async getStats() {
    return this.request('stats');
  }

  // ==================== AUTH API ====================

  /**
   * Register new user
   */
  async register(username, email, password, fullName = null) {
    return this.request('auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username,
        email,
        password,
        full_name: fullName,
      }),
    });
  }

  /**
   * Login user
   */
  async login(username, password) {
    return this.request('auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  }

  /**
   * Get current user profile
   */
  async getCurrentUser() {
    return this.request('auth/me');
  }

  /**
   * Create API key
   */
  async createAPIKey(keyName, scopes, tier = 'basic') {
    return this.request('auth/api-keys', {
      method: 'POST',
      body: JSON.stringify({
        key_name: keyName,
        scopes,
        tier,
      }),
    });
  }

  /**
   * List API keys
   */
  async listAPIKeys() {
    return this.request('auth/api-keys');
  }

  /**
   * Revoke API key
   */
  async revokeAPIKey(keyId) {
    return this.request(`auth/api-keys/${keyId}`, {
      method: 'DELETE',
    });
  }

  // ==================== HEALTH API ====================

  /**
   * Health check
   */
  async health() {
    return this.request('health');
  }
}

/**
 * Custom API Error
 */
class APIError extends Error {
  constructor(message, code, details = null) {
    super(message);
    this.name = 'APIError';
    this.code = code;
    this.details = details;
  }
}

/**
 * Global API client instance
 */
const apiClient = new ProspectIQClient({
  baseURL: 'http://localhost:8000',
  version: 'v1',
  timeout: 30000,
  retries: 3,
});

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ProspectIQClient, APIError, apiClient };
}
```

### Usage in Frontend

**Before (search.js):**
```javascript
const response = await fetch(`${API_BASE_URL}/regions?country=united+states`);
const data = await response.json();
const states = data.regions.map(r => r.region);
```

**After (with API client):**
```javascript
const data = await apiClient.getRegions('united states');
const states = data.regions.map(r => r.region);
```

**Before (results.js):**
```javascript
const params = new URLSearchParams();
params.set('q', currentParams.keyword || '');
// ... 20 lines of param building ...
const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`);
const data = await response.json();
```

**After (with API client):**
```javascript
const data = await apiClient.search({
  q: currentParams.keyword,
  regions: currentParams.states,
  industries: currentParams.industries,
  limit: currentLimit,
  offset: currentOffset,
});
```

---

## 4. Error Handling Strategy

### Current State: Inconsistent Error Handling

```javascript
// search.js - shows generic error
catch (error) {
  console.error('Failed to load filters:', error);
  container.innerHTML = '<p style="color: var(--error);">Error loading states</p>';
}

// results.js - shows error message
catch (error) {
  errorState.style.display = 'block';
  document.getElementById('errorMessage').textContent = error.message;
}
```

### Proposed: Centralized Error Handler

Create `frontend/error-handler.js`:

```javascript
/**
 * Centralized Error Handler
 * Consistent error display across the app
 */

class ErrorHandler {
  /**
   * Handle API errors with user-friendly messages
   */
  static handle(error, context = '') {
    console.error(`[${context}] Error:`, error);

    // Map error codes to user-friendly messages
    const errorMessages = {
      400: 'Invalid request. Please check your search parameters.',
      401: 'Authentication required. Please log in.',
      403: 'Access denied. You don\'t have permission for this action.',
      404: 'Resource not found.',
      429: 'Too many requests. Please wait a moment and try again.',
      500: 'Server error. Please try again later.',
      503: 'Service temporarily unavailable. Please try again later.',
      'TIMEOUT': 'Request timed out. The server may be busy processing data.',
      'NETWORK_ERROR': 'Network error. Please check your connection.',
      'VALIDATION_ERROR': 'Invalid input. Please check your data.',
    };

    let message = error.message;
    let suggestion = '';

    // Match error code
    if (error.code && errorMessages[error.code]) {
      message = errorMessages[error.code];
    }

    // Add context-specific suggestions
    if (error.code === 429) {
      suggestion = 'Rate limit exceeded. Try again in a few seconds.';
    } else if (error.code === 'TIMEOUT') {
      suggestion = 'The database may be loading. Try again in a few minutes.';
    } else if (error.code >= 500) {
      suggestion = 'If this persists, please contact support.';
    }

    return {
      message,
      suggestion,
      originalError: error,
    };
  }

  /**
   * Display error in UI
   */
  static display(error, containerId, options = {}) {
    const { message, suggestion } = this.handle(error, options.context);
    const container = document.getElementById(containerId);

    if (!container) {
      console.error('Error container not found:', containerId);
      return;
    }

    const retryButton = options.onRetry
      ? `<button onclick="${options.onRetry}" class="btn-primary" style="margin-top: 12px;">Retry</button>`
      : '';

    container.innerHTML = `
      <div class="error-message" style="
        padding: 20px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid var(--error);
        border-radius: 8px;
        color: var(--error);
      ">
        <strong>⚠️ ${message}</strong>
        ${suggestion ? `<p style="margin-top: 8px; color: var(--text-secondary);">${suggestion}</p>` : ''}
        ${retryButton}
      </div>
    `;
  }

  /**
   * Show toast notification
   */
  static toast(error, type = 'error') {
    const { message } = this.handle(error);

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'error' ? 'var(--error)' : 'var(--success)'};
      color: white;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      z-index: 10000;
      animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 5000);
  }
}

// CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(400px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(400px); opacity: 0; }
  }
`;
document.head.appendChild(style);
```

**Usage:**
```javascript
try {
  const data = await apiClient.search(params);
} catch (error) {
  ErrorHandler.display(error, 'errorContainer', {
    context: 'Search',
    onRetry: 'executeSearch()',
  });
}
```

---

## 5. Parameter Mapping & Validation

### The Bug We Need to Fix

**Frontend sends:**
```javascript
params.states = ['California', 'New York'];
```

**Backend expects:**
```python
regions: list[str] | None = Query(None)
```

**Result:** Filter silently ignored! 🐛

### Solution: Explicit Mapping Layer

Create `frontend/param-mapper.js`:

```javascript
/**
 * Parameter Mapper
 * Ensures frontend params match backend expectations
 */

class ParamMapper {
  /**
   * Map frontend search params to API params
   */
  static toAPISearchParams(frontendParams) {
    return {
      q: frontendParams.keyword || '',
      limit: frontendParams.limit || 20,
      offset: frontendParams.offset || 0,
      location_country: 'united states', // Always US for now

      // IMPORTANT: Frontend uses 'states', backend uses 'regions'
      regions: frontendParams.states || [],

      // Industries matches
      industries: frontendParams.industries || [],

      // Experience
      min_years_experience: frontendParams.min_experience
        ? parseInt(frontendParams.min_experience)
        : undefined,
      max_years_experience: frontendParams.max_experience
        ? parseInt(frontendParams.max_experience)
        : undefined,

      // Skills (split comma-separated string)
      skills: frontendParams.skills
        ? frontendParams.skills.split(',').map(s => s.trim()).filter(Boolean)
        : [],

      // Search weights
      vector_weight: 0.8,
      lexical_weight: 0.2,
      ef_search: 64,
    };
  }

  /**
   * Map API response to frontend format
   */
  static fromAPISearchResponse(apiResponse) {
    return {
      results: apiResponse.results.map(this.toFrontendProfile),
      totalCount: apiResponse.total_count,
      returnedCount: apiResponse.returned_count,
      offset: apiResponse.offset,
      limit: apiResponse.limit,
      queryTimeMs: apiResponse.query_time_ms,
      query: apiResponse.query,
      filtersApplied: this.toFrontendFilters(apiResponse.filters_applied),
      nextPageToken: apiResponse.next_page_token,
    };
  }

  /**
   * Convert API profile to frontend format
   */
  static toFrontendProfile(apiProfile) {
    return {
      id: apiProfile.id,
      fullName: apiProfile.full_name,
      firstName: apiProfile.first_name,
      lastName: apiProfile.last_name,
      jobTitle: apiProfile.job_title,
      companyName: apiProfile.company_name,
      industry: apiProfile.industry,
      location: apiProfile.location,
      country: apiProfile.location_country,
      region: apiProfile.region,
      city: apiProfile.locality,
      yearsExperience: apiProfile.years_experience,
      skills: apiProfile.skills || [],
      headline: apiProfile.headline,
      summary: apiProfile.summary,
      linkedinUrl: apiProfile.linkedin_url,
      email: apiProfile.email,
      phone: apiProfile.phone,
      website: apiProfile.website,
      twitter: apiProfile.twitter,
      github: apiProfile.github,
      score: apiProfile.score,
    };
  }

  /**
   * Convert API filters to frontend format
   */
  static toFrontendFilters(apiFilters) {
    const frontendFilters = {};

    if (apiFilters.regions) {
      frontendFilters.states = apiFilters.regions;
    }
    if (apiFilters.industries) {
      frontendFilters.industries = apiFilters.industries;
    }
    if (apiFilters.min_years_experience !== undefined) {
      frontendFilters.minExperience = apiFilters.min_years_experience;
    }
    if (apiFilters.max_years_experience !== undefined) {
      frontendFilters.maxExperience = apiFilters.max_years_experience;
    }
    if (apiFilters.skills) {
      frontendFilters.skills = apiFilters.skills;
    }

    return frontendFilters;
  }

  /**
   * Validate search params before sending
   */
  static validateSearchParams(params) {
    const errors = [];

    if (params.limit && (params.limit < 1 || params.limit > 1000)) {
      errors.push('Limit must be between 1 and 1000');
    }

    if (params.offset && params.offset < 0) {
      errors.push('Offset cannot be negative');
    }

    if (params.min_years_experience && params.max_years_experience) {
      if (params.min_years_experience > params.max_years_experience) {
        errors.push('Min experience cannot exceed max experience');
      }
    }

    if (params.min_years_experience && (params.min_years_experience < 0 || params.min_years_experience > 80)) {
      errors.push('Min experience must be between 0 and 80');
    }

    if (params.max_years_experience && (params.max_years_experience < 0 || params.max_years_experience > 80)) {
      errors.push('Max experience must be between 0 and 80');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}
```

**Updated search.js:**
```javascript
// Build params
const frontendParams = {
  keyword: formData.get('keyword'),
  states: getSelectedStates(),        // Frontend naming
  industries: getSelectedIndustries(),
  min_experience: formData.get('min_experience'),
  max_experience: formData.get('max_experience'),
  skills: formData.get('skills'),
  limit: 100,
  offset: 0,
};

// Validate
const validation = ParamMapper.validateSearchParams(frontendParams);
if (!validation.valid) {
  alert('Invalid search parameters:\n' + validation.errors.join('\n'));
  return;
}

// Map to API format
const apiParams = ParamMapper.toAPISearchParams(frontendParams);

// Make request
const apiResponse = await apiClient.search(apiParams);

// Map back to frontend format
const data = ParamMapper.fromAPISearchResponse(apiResponse);
```

---

## 6. Backend API Structure

### Proposed Endpoint Organization

```
/v1/
├── search
│   ├── GET  /search                 # Hybrid search
│   └── POST /search                 # Same (supports POST body)
│
├── filters/
│   ├── GET /filters/countries       # List countries
│   ├── GET /filters/regions         # List regions/states
│   ├── GET /filters/industries      # List industries
│   └── GET /filters/localities      # List cities
│
├── export/
│   ├── GET /export/csv              # Export to CSV
│   └── GET /export/ndjson           # Export to NDJSON
│
├── profiles/
│   ├── GET /profiles/{id}           # Get single profile
│   └── GET /profiles/{id}/similar   # Find similar profiles
│
├── auth/
│   ├── POST /auth/register          # Register user
│   ├── POST /auth/login             # Login user
│   ├── POST /auth/refresh           # Refresh token
│   ├── GET  /auth/me                # Get current user
│   ├── GET  /auth/api-keys          # List API keys
│   ├── POST /auth/api-keys          # Create API key
│   └── DELETE /auth/api-keys/{id}   # Revoke API key
│
├── stats/
│   └── GET /stats                   # Dataset statistics
│
└── health/
    └── GET /health                  # Health check
```

### Grouping by Feature (FastAPI Routers)

**Current:** Everything in `app.py` (783 lines)

**Proposed:**
```
backend/api/
├── app.py                    # Main app, lifespan, CORS
├── routers/
│   ├── __init__.py
│   ├── search.py             # Search endpoints
│   ├── filters.py            # Filter endpoints
│   ├── export.py             # Export endpoints
│   ├── auth.py               # Auth endpoints (already exists)
│   ├── profiles.py           # Profile endpoints
│   └── stats.py              # Stats endpoints
├── models/
│   ├── __init__.py
│   ├── search.py             # Search models
│   ├── profile.py            # Profile models
│   └── auth.py               # Auth models (already exists)
├── services/
│   ├── __init__.py
│   ├── search_service.py     # Search logic
│   ├── filter_service.py     # Filter logic
│   └── auth_service.py       # Auth logic
└── middleware/
    ├── __init__.py
    ├── auth.py               # Auth middleware (exists)
    ├── rate_limit.py         # Rate limiting (exists)
    └── logging.py            # Request logging
```

**Example: `backend/api/routers/filters.py`**
```python
from fastapi import APIRouter, Response, Query
from typing import Optional

router = APIRouter(prefix="/v1/filters", tags=["Filters"])

@router.get("/regions")
async def get_regions(
    response: Response,
    country: Optional[str] = Query(None, description="Filter by country")
):
    """Get list of regions/states"""
    # Implementation...
    return {"regions": [...]}

@router.get("/industries")
async def get_industries(response: Response):
    """Get list of industries"""
    # Implementation...
    return {"industries": [...]}

@router.get("/countries")
async def get_countries(response: Response):
    """Get list of countries"""
    # Implementation...
    return {"countries": [...]}
```

**In `app.py`:**
```python
from backend.api.routers import filters, search, export, auth, stats

app.include_router(filters.router)
app.include_router(search.router)
app.include_router(export.router)
app.include_router(auth.router)
app.include_router(stats.router)
```

---

## 7. Testing Strategy

### Unit Tests for API Client

Create `frontend/tests/api-client.test.js`:

```javascript
describe('ProspectIQClient', () => {
  let client;

  beforeEach(() => {
    client = new ProspectIQClient({
      baseURL: 'http://localhost:8000',
      version: 'v1',
    });
  });

  describe('search()', () => {
    it('should build correct query string', async () => {
      const params = {
        q: 'software engineer',
        regions: ['California', 'New York'],
        industries: ['Technology'],
        limit: 20,
        offset: 0,
      };

      // Mock fetch
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ results: [], total_count: 0 }),
        })
      );

      await client.search(params);

      const calledUrl = global.fetch.mock.calls[0][0];
      expect(calledUrl).toContain('q=software+engineer');
      expect(calledUrl).toContain('regions=California');
      expect(calledUrl).toContain('regions=New+York');
      expect(calledUrl).toContain('industries=Technology');
      expect(calledUrl).toContain('limit=20');
    });

    it('should validate limit parameter', async () => {
      await expect(
        client.search({ limit: 2000 })
      ).rejects.toThrow('Limit must be between 1 and 1000');
    });

    it('should retry on timeout', async () => {
      client.retries = 2;

      global.fetch = jest.fn(() =>
        Promise.reject(new Error('AbortError'))
      );

      await expect(client.search({})).rejects.toThrow('Request timeout');

      // Should have retried 2 times
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
  });

  describe('ParamMapper', () => {
    it('should map frontend params to API params', () => {
      const frontendParams = {
        keyword: 'engineer',
        states: ['CA', 'NY'],
        industries: ['Tech'],
        min_experience: '5',
        max_experience: '10',
      };

      const apiParams = ParamMapper.toAPISearchParams(frontendParams);

      expect(apiParams.q).toBe('engineer');
      expect(apiParams.regions).toEqual(['CA', 'NY']);
      expect(apiParams.industries).toEqual(['Tech']);
      expect(apiParams.min_years_experience).toBe(5);
      expect(apiParams.max_years_experience).toBe(10);
    });

    it('should validate experience range', () => {
      const params = {
        min_years_experience: 10,
        max_years_experience: 5,
      };

      const result = ParamMapper.validateSearchParams(params);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Min experience cannot exceed max experience');
    });
  });
});
```

### Integration Tests

Create `backend/tests/test_api_integration.py`:

```python
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)

def test_search_with_regions():
    """Test that regions filter works correctly"""
    response = client.get(
        "/v1/search",
        params={
            "q": "software engineer",
            "regions": ["California", "New York"],
            "limit": 10,
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    assert "total_count" in data
    assert data["returned_count"] <= 10

    # Verify filters were applied
    assert "regions" in data["filters_applied"]
    assert "California" in data["filters_applied"]["regions"]

def test_search_invalid_limit():
    """Test that invalid limit returns 422"""
    response = client.get(
        "/v1/search",
        params={"limit": 2000}
    )

    assert response.status_code == 422

def test_export_requires_filter():
    """Test that export requires filter or query"""
    response = client.get("/v1/export/csv")

    assert response.status_code == 422
    assert "requires query or at least one filter" in response.text.lower()

def test_filter_endpoints():
    """Test that filter endpoints return data"""
    # Regions
    response = client.get("/v1/filters/regions?country=united+states")
    assert response.status_code == 200
    data = response.json()
    assert "regions" in data
    assert len(data["regions"]) > 0

    # Industries
    response = client.get("/v1/filters/industries")
    assert response.status_code == 200
    data = response.json()
    assert "industries" in data
    assert len(data["industries"]) > 0
```

---

## 8. Documentation & Developer Experience

### Auto-Generated API Docs

FastAPI already provides:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

**Improvements:**
1. Add descriptions to all endpoints
2. Add examples to all models
3. Add response examples
4. Document error codes

**Example:**
```python
@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search for talent profiles",
    description="""
    Execute hybrid semantic search on talent profiles.

    Combines vector similarity search (HNSW) with full-text lexical search (ts_rank).

    **Features:**
    - Semantic understanding (e.g., "ML expert" matches "Machine Learning Engineer")
    - Multi-filter support (regions, industries, skills, experience)
    - Pagination with opaque tokens
    - Relevance scoring

    **Rate Limits:**
    - Public: 60 requests/min
    - Basic: 200 requests/min
    - Trusted: 1000 requests/min
    """,
    responses={
        200: {
            "description": "Search results",
            "content": {
                "application/json": {
                    "example": {
                        "results": [...],
                        "total_count": 1234,
                        "returned_count": 20,
                        "query_time_ms": 145.3
                    }
                }
            }
        },
        400: {"description": "Invalid request parameters"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    tags=["Search"]
)
async def search_profiles(...):
    pass
```

### Client SDK Generation

Use `openapi-generator` to auto-generate client SDKs:

```bash
# JavaScript/TypeScript
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-fetch \
  -o frontend/sdk

# Python (for API consumers)
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o python-sdk

# Postman Collection
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g postman-collection \
  -o postman
```

### Interactive API Explorer

Create `frontend/api-explorer.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <title>PROSPECTIQ API Explorer</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>

  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: 'http://localhost:8000/openapi.json',
      dom_id: '#swagger-ui',
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset
      ],
      layout: "BaseLayout",
      deepLinking: true,
      tryItOutEnabled: true,
    });
  </script>
</body>
</html>
```

---

## 9. Migration Plan

### Phase 1: Non-Breaking Changes (Week 1)

1. **Add API versioning** (`/v1/` prefix)
   - Keep old endpoints working
   - Redirect `/search` → `/v1/search`
   - Update frontend to use `/v1/` endpoints

2. **Create API client library**
   - Implement `frontend/api-client.js`
   - Add to `search.js` (test with one endpoint)
   - Gradually migrate other files

3. **Add parameter mapper**
   - Implement `frontend/param-mapper.js`
   - Fix `states` → `regions` bug
   - Add validation

### Phase 2: Frontend Refactor (Week 2)

1. **Migrate all frontend files to API client**
   - search.js
   - results.js
   - dashboard.js
   - auth.js

2. **Add error handler**
   - Implement `frontend/error-handler.js`
   - Replace all error handling

3. **Add tests**
   - Unit tests for API client
   - Integration tests for critical paths

### Phase 3: Backend Refactor (Week 3)

1. **Split into routers**
   - `routers/search.py`
   - `routers/filters.py`
   - `routers/export.py`
   - `routers/stats.py`

2. **Extract services**
   - `services/search_service.py`
   - `services/filter_service.py`

3. **Improve documentation**
   - Add descriptions to all endpoints
   - Add examples
   - Document error codes

### Phase 4: Testing & Validation (Week 4)

1. **Write comprehensive tests**
   - Backend integration tests
   - Frontend unit tests
   - End-to-end tests

2. **Load testing**
   - Test with 1000+ concurrent users
   - Identify bottlenecks
   - Optimize slow queries

3. **Documentation**
   - Update API docs
   - Write migration guide
   - Create video tutorials

---

## 10. Success Metrics

### How We'll Know It's Working

1. **Zero Breaking Changes**
   - Frontend updates don't break existing functionality
   - Backend updates don't break frontend

2. **Fast Development**
   - New features take 50% less time
   - Fewer bugs in production
   - Easier onboarding for new developers

3. **Reliability**
   - 99.9% uptime
   - < 1% error rate
   - < 500ms average response time

4. **Developer Experience**
   - Clear error messages
   - Auto-complete in IDE (TypeScript types)
   - Self-documenting code

### Monitoring Dashboard

Track in real-time:
- API response times (p50, p95, p99)
- Error rates by endpoint
- Rate limit hits
- Most used filters
- Search query patterns

---

## 11. Comparison: Before vs After

### Before (Current State)

**Frontend:**
```javascript
// Hardcoded URL
const API_BASE_URL = 'http://localhost:8000';

// Manual parameter building (bug-prone)
const params = new URLSearchParams();
params.set('q', query);
params.append('regions', 'California');  // Wait, is it 'regions' or 'states'?

// Manual fetch (no retries)
const response = await fetch(`${API_BASE_URL}/search?${params}`);

// No error handling
const data = await response.json();
```

**Backend:**
```python
# No versioning
@app.get("/search")

# Scattered in one huge file (783 lines)

# Inconsistent parameter names
regions: list[str] | None = Query(None)  # Frontend sends 'states'
```

### After (Proposed)

**Frontend:**
```javascript
// Centralized client
import { apiClient } from './api-client.js';

// Type-safe params (if using TypeScript)
const params: SearchRequest = {
  q: 'software engineer',
  regions: ['California', 'New York'],  // Clear naming
  industries: ['Technology'],
  limit: 20,
};

// Automatic retries, error handling, validation
try {
  const data = await apiClient.search(params);
} catch (error) {
  ErrorHandler.display(error, 'errorContainer');
}
```

**Backend:**
```python
# Versioned
@router.get("/v1/search")

# Organized by feature
from backend.api.routers import search

# Consistent, documented
@router.get(
    "/v1/search",
    summary="Search profiles",
    description="Hybrid semantic + lexical search",
    response_model=SearchResponse,
)
async def search_profiles(request: SearchRequest):
    return await search_service.execute(request)
```

---

## 12. Questions & Decisions Needed

### Before Implementation

1. **Versioning Strategy**
   - ✅ URL-based (`/v1/`, `/v2/`) - RECOMMENDED
   - ❌ Header-based (`Accept: application/vnd.prospectiq.v1+json`)
   - ❌ Query param (`?version=1`)

2. **TypeScript Migration**
   - ✅ Migrate frontend to TypeScript for type safety
   - ❌ Stay with vanilla JS but use JSDoc comments
   - ❌ Hybrid: API client in TS, rest in JS

3. **Testing Framework**
   - ✅ Jest (JavaScript)
   - ❌ Mocha/Chai
   - ✅ pytest (Python)

4. **API Documentation**
   - ✅ Keep using FastAPI's built-in Swagger UI
   - ❌ Build custom docs site
   - ✅ Add README with examples

5. **Monitoring**
   - ✅ Add logging middleware
   - ❌ Integrate with external monitoring (Sentry, DataDog)
   - ✅ Simple metrics dashboard

---

## Summary

This proposal creates a **rock-solid API foundation** that:

✅ **Won't break** when we make changes (versioning + contracts)
✅ **Catches bugs early** (validation + testing)
✅ **Easy to use** (client library + error handling)
✅ **Well-documented** (OpenAPI + examples)
✅ **Production-ready** (retries + rate limiting + monitoring)

### Next Steps

1. **Review this proposal** - Let me know what you think
2. **Make decisions** on open questions (section 12)
3. **Start Phase 1** - Add versioning + API client
4. **Test thoroughly** before deploying
5. **Iterate** based on real-world usage

---

**Ready to implement?** Let me know which parts you want to prioritize!
