// Strava Bike Tracker - Main Application Logic

class StravaBikeTracker {
    constructor() {
        this.accessToken = null;
        this.userInfo = null;
        this.bikes = new Map();
        this.activities = [];
        
        this.initializeApp();
    }

    async initializeApp() {
        // Set up event listeners
        this.setupEventListeners();
        
        // Set default dates
        DateUtils.setDefaultDates();
        
        // Check for OAuth callback
        await this.handleOAuthCallback();
        
        // Check for existing token
        await this.checkExistingAuth();
    }

    setupEventListeners() {
        document.getElementById('login-btn').addEventListener('click', () => this.initiateStravaAuth());
        document.getElementById('change-account-btn').addEventListener('click', () => this.logout());
        document.getElementById('fetch-data-btn').addEventListener('click', () => this.fetchBikeData());
        document.getElementById('retry-btn').addEventListener('click', () => this.hideError());
    }

    // OAuth Flow
    initiateStravaAuth() {
        const state = Math.random().toString(36).substring(2, 15);
        sessionStorage.setItem('oauth_state', state);
        
        const authUrl = new URL(STRAVA_CONFIG.AUTHORIZE_URL);
        authUrl.searchParams.append('client_id', STRAVA_CONFIG.CLIENT_ID);
        authUrl.searchParams.append('redirect_uri', STRAVA_CONFIG.REDIRECT_URI);
        authUrl.searchParams.append('response_type', 'code');
        authUrl.searchParams.append('scope', STRAVA_CONFIG.SCOPE);
        authUrl.searchParams.append('state', state);
        
        window.location.href = authUrl.toString();
    }

    async handleOAuthCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const error = urlParams.get('error');

        if (error) {
            this.showError(`Authorization failed: ${error}`);
            return;
        }

        if (code && state) {
            const storedState = sessionStorage.getItem('oauth_state');
            if (state !== storedState) {
                this.showError('Invalid state parameter. Possible CSRF attack.');
                return;
            }

            // Clear the state
            sessionStorage.removeItem('oauth_state');
            
            // Exchange code for token
            await this.exchangeCodeForToken(code);
            
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }

    async exchangeCodeForToken(code) {
        try {
            this.showLoading();
            
            const response = await fetch(STRAVA_CONFIG.TOKEN_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_id: STRAVA_CONFIG.CLIENT_ID,
                    client_secret: 'd04752bfd85be50fa072a6ec6f6134e57a4b6247', // Should ideally not be here... whatever
                    code: code,
                    grant_type: 'authorization_code'
                })
            });

            if (!response.ok) {
                throw new Error('Failed to exchange code for token');
            }

            const tokenData = await response.json();
            
            // Store tokens and user info
            TokenManager.setTokens(tokenData);
            TokenManager.setUserInfo(tokenData.athlete);
            
            this.accessToken = tokenData.access_token;
            this.userInfo = tokenData.athlete;
            
            this.showUserInfo();
            this.hideLoading();
            
        } catch (error) {
            console.error('Token exchange error:', error);
            this.showError('Failed to complete authentication. Please try again.');
        }
    }

    async checkExistingAuth() {
        const storedToken = TokenManager.getAccessToken();
        const storedUserInfo = TokenManager.getUserInfo();
        
        if (storedToken && storedUserInfo && !TokenManager.isTokenExpired()) {
            this.accessToken = storedToken;
            this.userInfo = storedUserInfo;
            this.showUserInfo();
        } else if (storedToken && TokenManager.isTokenExpired()) {
            // Try to refresh token
            await this.refreshAccessToken();
        }
    }

    async refreshAccessToken() {
        const refreshToken = TokenManager.getRefreshToken();
        if (!refreshToken) {
            this.logout();
            return;
        }

        try {
            const response = await fetch(STRAVA_CONFIG.TOKEN_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_id: STRAVA_CONFIG.CLIENT_ID,
                    client_secret: 'd04752bfd85be50fa072a6ec6f6134e57a4b6247', // Should ideally not be here... whatever
                    refresh_token: refreshToken,
                    grant_type: 'refresh_token'
                })
            });

            if (!response.ok) {
                throw new Error('Failed to refresh token');
            }

            const tokenData = await response.json();
            TokenManager.setTokens(tokenData);
            
            this.accessToken = tokenData.access_token;
            this.showUserInfo();
            
        } catch (error) {
            console.error('Token refresh error:', error);
            this.logout();
        }
    }

    logout() {
        TokenManager.clearTokens();
        this.accessToken = null;
        this.userInfo = null;
        this.bikes.clear();
        this.activities = [];
        
        this.showLoginSection();
        this.hideResults();
        this.hideError();
    }

    // API Calls
    async fetchBikeData() {
        if (!this.accessToken) {
            this.showError('Please connect your Strava account first.');
            return;
        }

        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        if (!startDate || !endDate) {
            this.showError('Please select both start and end dates.');
            return;
        }

        if (new Date(startDate) > new Date(endDate)) {
            this.showError('Start date must be before end date.');
            return;
        }

        try {
            this.showLoading();
            this.hideError();
            this.hideResults();

            // Fetch gear (bikes)
            await this.fetchGear();
            
            // Fetch activities in the date range
            await this.fetchActivities(startDate, endDate);
            
            // Calculate and display results
            this.calculateBikeDistances();
            this.displayResults();
            
        } catch (error) {
            console.error('Error fetching bike data:', error);
            this.showError('Failed to fetch data from Strava. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async fetchGear() {
        const response = await fetch(`${STRAVA_CONFIG.API_BASE_URL}/athlete`, {
            headers: {
                'Authorization': `Bearer ${this.accessToken}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch athlete data');
        }

        const athlete = await response.json();
        
        // Store bikes
        if (athlete.bikes) {
            athlete.bikes.forEach(bike => {
                this.bikes.set(bike.id, {
                    ...bike,
                    distance: 0,
                    rides: 0,
                    elevation: 0
                });
            });
        }
    }

    async fetchActivities(startDate, endDate) {
        const startTimestamp = Math.floor(new Date(startDate).getTime() / 1000);
        const endTimestamp = Math.floor(new Date(endDate + 'T23:59:59').getTime() / 1000);
        
        let page = 1;
        let allActivities = [];
        
        while (true) {
            const response = await fetch(
                `${STRAVA_CONFIG.API_BASE_URL}/athlete/activities?after=${startTimestamp}&before=${endTimestamp}&page=${page}&per_page=200`,
                {
                    headers: {
                        'Authorization': `Bearer ${this.accessToken}`
                    }
                }
            );

            if (!response.ok) {
                throw new Error('Failed to fetch activities');
            }

            const activities = await response.json();
            
            if (activities.length === 0) break;
            
            // Filter for cycling activities only
            const cyclingActivities = activities.filter(activity => 
                activity.type === 'Ride' || activity.sport_type === 'Ride' || activity.type === 'Virtual Ride' || activity.sport_type === 'Virtual Ride'
            );
            
            allActivities = allActivities.concat(cyclingActivities);
            page++;
            
            // Break if we got less than 200 activities (last page)
            if (activities.length < 200) break;
        }
        
        this.activities = allActivities;
    }

    calculateBikeDistances() {
        // Reset bike data
        this.bikes.forEach(bike => {
            bike.distance = 0;
            bike.rides = 0;
            bike.elevation = 0;
        });

        // Calculate distances for each bike
        this.activities.forEach(activity => {
            if (activity.gear_id && this.bikes.has(activity.gear_id)) {
                const bike = this.bikes.get(activity.gear_id);
                bike.distance += activity.distance || 0;
                bike.rides += 1;
                bike.elevation += activity.total_elevation_gain || 0;
            }
        });
    }

    // UI Management
    showLoginSection() {
        document.getElementById('auth-section').classList.remove('hidden');
        document.getElementById('login-section').classList.remove('hidden');
        document.getElementById('user-info').classList.add('hidden');
        document.getElementById('date-section').classList.add('hidden');
    }

    showUserInfo() {
        if (!this.userInfo) return;
        
        document.getElementById('user-name').textContent = `${this.userInfo.firstname} ${this.userInfo.lastname}`;
        document.getElementById('user-location').textContent = this.userInfo.city || 'Location not available';
        document.getElementById('user-avatar').src = this.userInfo.profile || 'https://via.placeholder.com/60';
        
        document.getElementById('login-section').classList.add('hidden');
        document.getElementById('user-info').classList.remove('hidden');
        document.getElementById('date-section').classList.remove('hidden');
    }

    showLoading() {
        document.getElementById('loading-section').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loading-section').classList.add('hidden');
    }

    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-section').classList.remove('hidden');
    }

    hideError() {
        document.getElementById('error-section').classList.add('hidden');
    }

    hideResults() {
        document.getElementById('results-section').classList.add('hidden');
    }

    displayResults() {
        // Calculate totals
        let totalDistance = 0;
        let totalRides = 0;
        let totalBikes = 0;

        this.bikes.forEach(bike => {
            if (bike.rides > 0) {
                totalDistance += bike.distance;
                totalRides += bike.rides;
                totalBikes++;
            }
        });

        // Update summary stats
        document.getElementById('total-bikes').textContent = totalBikes;
        document.getElementById('total-distance').textContent = DistanceUtils.formatDistance(totalDistance);
        document.getElementById('total-rides').textContent = totalRides;

        // Display individual bikes
        this.displayBikes();

        // Show results section
        document.getElementById('results-section').classList.remove('hidden');
    }

    displayBikes() {
        const bikesContainer = document.getElementById('bikes-list');
        bikesContainer.innerHTML = '';

        // Convert bikes to array and sort by distance
        const bikeArray = Array.from(this.bikes.values())
            .filter(bike => bike.rides > 0)
            .sort((a, b) => b.distance - a.distance);

        if (bikeArray.length === 0) {
            bikesContainer.innerHTML = `
                <div class="bike-card">
                    <p>No bike rides found in the selected date range.</p>
                </div>
            `;
            return;
        }

        bikeArray.forEach(bike => {
            const bikeCard = document.createElement('div');
            bikeCard.className = 'bike-card';
            
            bikeCard.innerHTML = `
                <div class="bike-header">
                    <div class="bike-name">
                        <i class="fas fa-bicycle"></i>
                        ${bike.name}
                    </div>
                    <div class="bike-distance">
                        ${DistanceUtils.formatDistance(bike.distance)}
                    </div>
                </div>
                <div class="bike-stats">
                    <div class="bike-stat">
                        <div class="bike-stat-value">${bike.rides}</div>
                        <div class="bike-stat-label">Rides</div>
                    </div>
                    <div class="bike-stat">
                        <div class="bike-stat-value">${DistanceUtils.formatElevation(bike.elevation)}</div>
                        <div class="bike-stat-label">Elevation</div>
                    </div>
                    <div class="bike-stat">
                        <div class="bike-stat-value">${DistanceUtils.formatDistance(bike.distance / bike.rides)}</div>
                        <div class="bike-stat-label">Avg per ride</div>
                    </div>
                </div>
            `;
            
            bikesContainer.appendChild(bikeCard);
        });
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Check if config is properly set up
    if (STRAVA_CONFIG.CLIENT_ID === 'YOUR_STRAVA_CLIENT_ID') {
        document.body.innerHTML = `
            <div style="padding: 20px; text-align: center; font-family: Arial, sans-serif;">
                <h1>⚠️ Configuration Required</h1>
                <p>Please set up your Strava API credentials in <code>config.js</code></p>
                <ol style="text-align: left; max-width: 600px; margin: 20px auto;">
                    <li>Go to <a href="https://www.strava.com/settings/api" target="_blank">Strava API Settings</a></li>
                    <li>Create a new application</li>
                    <li>Copy your Client ID and Client Secret</li>
                    <li>Update the <code>CLIENT_ID</code> in <code>config.js</code></li>
                    <li>Set up a backend service for the Client Secret (required for production)</li>
                </ol>
            </div>
        `;
        return;
    }
    
    new StravaBikeTracker();
});
