// Strava API Configuration
const STRAVA_CONFIG = {
    // You'll need to replace this with your actual Strava app client ID
    // Register your app at: https://www.strava.com/settings/api
    CLIENT_ID: '171148',
    
    // The redirect URI must match exactly what you set in your Strava app settings
    // For GitHub Pages, this will be: https://yourusername.github.io/strava-bike-tracker/
    REDIRECT_URI: window.location.origin + window.location.pathname,
    
    // Strava API endpoints
    AUTHORIZE_URL: 'https://www.strava.com/oauth/authorize',
    TOKEN_URL: 'https://www.strava.com/oauth/token',
    API_BASE_URL: 'https://www.strava.com/api/v3',
    
    // OAuth scopes - we need activity:read to access activities
    SCOPE: 'activity:read_all,profile:read_all',
    
    // Local storage keys
    STORAGE_KEYS: {
        ACCESS_TOKEN: 'strava_access_token',
        REFRESH_TOKEN: 'strava_refresh_token',
        EXPIRES_AT: 'strava_expires_at',
        USER_INFO: 'strava_user_info',
        LAST_ACCOUNT: 'strava_last_account'
    }
};

// Utility functions for token management
const TokenManager = {
    setTokens(tokenData) {
        localStorage.setItem(STRAVA_CONFIG.STORAGE_KEYS.ACCESS_TOKEN, tokenData.access_token);
        localStorage.setItem(STRAVA_CONFIG.STORAGE_KEYS.REFRESH_TOKEN, tokenData.refresh_token);
        localStorage.setItem(STRAVA_CONFIG.STORAGE_KEYS.EXPIRES_AT, tokenData.expires_at);
    },
    
    getAccessToken() {
        return localStorage.getItem(STRAVA_CONFIG.STORAGE_KEYS.ACCESS_TOKEN);
    },
    
    getRefreshToken() {
        return localStorage.getItem(STRAVA_CONFIG.STORAGE_KEYS.REFRESH_TOKEN);
    },
    
    getExpiresAt() {
        return parseInt(localStorage.getItem(STRAVA_CONFIG.STORAGE_KEYS.EXPIRES_AT));
    },
    
    isTokenExpired() {
        const expiresAt = this.getExpiresAt();
        if (!expiresAt) return true;
        return Date.now() / 1000 > expiresAt;
    },
    
    clearTokens() {
        localStorage.removeItem(STRAVA_CONFIG.STORAGE_KEYS.ACCESS_TOKEN);
        localStorage.removeItem(STRAVA_CONFIG.STORAGE_KEYS.REFRESH_TOKEN);
        localStorage.removeItem(STRAVA_CONFIG.STORAGE_KEYS.EXPIRES_AT);
        localStorage.removeItem(STRAVA_CONFIG.STORAGE_KEYS.USER_INFO);
    },
    
    setUserInfo(userInfo) {
        localStorage.setItem(STRAVA_CONFIG.STORAGE_KEYS.USER_INFO, JSON.stringify(userInfo));
        localStorage.setItem(STRAVA_CONFIG.STORAGE_KEYS.LAST_ACCOUNT, userInfo.id);
    },
    
    getUserInfo() {
        const userInfoStr = localStorage.getItem(STRAVA_CONFIG.STORAGE_KEYS.USER_INFO);
        return userInfoStr ? JSON.parse(userInfoStr) : null;
    },
    
    getLastAccountId() {
        return localStorage.getItem(STRAVA_CONFIG.STORAGE_KEYS.LAST_ACCOUNT);
    }
};

// Distance conversion utilities
const DistanceUtils = {
    metersToMiles(meters) {
        return meters * 0.000621371;
    },
    
    formatDistance(meters, unit = 'kilometers') {
        if (unit === 'miles') {
            const miles = this.metersToMiles(meters);
            return miles.toFixed(1) + ' mi';
        }
        return (meters / 1000).toFixed(1) + ' km';
    },
    
    formatElevation(meters, unit = 'meters') {
        if (unit === 'feet') {
            const feet = meters * 3.28084;
            return Math.round(feet) + ' ft';
        }
        return Math.round(meters) + ' m';
    },
    
    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }
};

// Date utilities
const DateUtils = {
    formatDate(date) {
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },
    
    toISODateString(date) {
        return date.toISOString().split('T')[0];
    },
    
    fromISODateString(dateString) {
        return new Date(dateString + 'T00:00:00');
    },
    
    setDefaultDates() {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setMonth(startDate.getMonth() - 3); // Default to 3 months ago
        
        document.getElementById('end-date').value = this.toISODateString(endDate);
        document.getElementById('start-date').value = this.toISODateString(startDate);
    }
};
