// Garmin coaching data for the static site.
// Live path: PROXY_BASE or same-origin /api/coach (FastAPI).
// GitHub Pages fallback: coach.json (refreshed by Actions).

const GarminCoach = {
    snapshot: null,

    isoDate(d) {
        return d.toISOString().slice(0, 10);
    },

    rangeForDays(days) {
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - (Math.max(days, 1) - 1));
        return { start: this.isoDate(start), end: this.isoDate(end) };
    },

    coachApiBase() {
        const configured = (GARMIN_CONFIG.PROXY_BASE || '').replace(/\/$/, '');
        if (configured) return configured;
        // Same-origin FastAPI when the site is served by uvicorn/app.py
        return '';
    },

    async fetchLive(days = GARMIN_CONFIG.DEFAULT_DAYS) {
        const base = this.coachApiBase();
        const url = `${base}/api/coach?days=${encodeURIComponent(days)}`;
        const response = await fetch(url, {
            headers: {
                // Optional: server can ignore this and use env; useful if proxy trusts client key
                'X-Garmin-Api-Key': GARMIN_CONFIG.PERSONAL_API_KEY
            }
        });
        if (!response.ok) {
            const detail = await response.text();
            throw new Error(`Coach API ${response.status}: ${detail.slice(0, 200)}`);
        }
        return response.json();
    },

    async fetchFallback() {
        const response = await fetch(GARMIN_CONFIG.FALLBACK_JSON, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Missing ${GARMIN_CONFIG.FALLBACK_JSON} (${response.status})`);
        }
        return response.json();
    },

    async load(days = GARMIN_CONFIG.DEFAULT_DAYS) {
        // Prefer live API; fall back to committed coach.json (GitHub Pages).
        try {
            this.snapshot = await this.fetchLive(days);
            this.snapshot._source = 'live';
            return this.snapshot;
        } catch (liveErr) {
            console.warn('Live Garmin coach fetch failed, trying fallback JSON:', liveErr);
            try {
                this.snapshot = await this.fetchFallback();
                this.snapshot._source = 'fallback';
                this.snapshot._liveError = String(liveErr.message || liveErr);
                return this.snapshot;
            } catch (fallbackErr) {
                throw new Error(
                    `Could not load Garmin data. Live: ${liveErr.message}. ` +
                    `Fallback: ${fallbackErr.message}`
                );
            }
        }
    },

    fmt(n, digits = 1) {
        if (n === null || n === undefined || Number.isNaN(n)) return '—';
        return Number(n).toFixed(digits);
    },

    display(snapshot) {
        const root = document.getElementById('garmin-results');
        const meta = document.getElementById('garmin-meta');
        const list = document.getElementById('garmin-activities');
        if (!root || !snapshot) return;

        const agg = snapshot.aggregates || {};
        const recovery = agg.recovery || {};
        const range = snapshot.range || {};
        const sourceLabel = snapshot._source === 'live'
            ? 'Live from Garmin'
            : 'Cached coach.json (GitHub Pages fallback)';

        meta.textContent = `${sourceLabel} · ${range.start || '?'} → ${range.end || '?'}` +
            (snapshot.fetched_at ? ` · fetched ${new Date(snapshot.fetched_at).toLocaleString()}` : '');

        document.getElementById('g-activity-count').textContent = agg.activity_count ?? 0;
        document.getElementById('g-distance').textContent =
            `${this.fmt(agg.total_distance_km, 1)} km`;
        document.getElementById('g-load').textContent = this.fmt(agg.total_training_load, 0);
        document.getElementById('g-recovery').textContent =
            (recovery.qualitative || 'unknown').toString();

        document.getElementById('g-sleep').textContent = this.fmt(recovery.sleep_score, 0);
        document.getElementById('g-hrv').textContent =
            recovery.hrv_last_night_ms != null ? `${this.fmt(recovery.hrv_last_night_ms, 0)} ms` : '—';
        document.getElementById('g-body-battery').textContent =
            recovery.body_battery_high != null ? this.fmt(recovery.body_battery_high, 0) : '—';
        document.getElementById('g-stress').textContent =
            recovery.stress_avg != null ? this.fmt(recovery.stress_avg, 0) : '—';

        const avail = snapshot.availability || {};
        const availEl = document.getElementById('garmin-availability');
        availEl.innerHTML = Object.keys(avail).map((k) => {
            const status = avail[k]?.status || 'unknown';
            return `<span class="avail-pill avail-${status}">${k}: ${status}</span>`;
        }).join('');

        const notes = document.getElementById('garmin-notes');
        const noteList = [...(snapshot.notes || [])];
        if (snapshot._liveError) {
            noteList.unshift(`Live API unavailable (${snapshot._liveError}). Showing cached data.`);
        }
        notes.innerHTML = noteList.length
            ? `<ul>${noteList.map((n) => `<li>${n}</li>`).join('')}</ul>`
            : '';

        const activities = snapshot.activities || [];
        if (!activities.length) {
            list.innerHTML = '<p class="muted">No activities in this range.</p>';
        } else {
            list.innerHTML = activities.map((a) => `
                <div class="bike-card">
                    <div class="bike-header">
                        <div class="bike-name">
                            <i class="fas fa-heartbeat"></i>
                            ${a.name || a.type || 'Activity'}
                        </div>
                        <div class="bike-distance">
                            ${a.distance_km != null ? `${this.fmt(a.distance_km, 1)} km` : '—'}
                        </div>
                    </div>
                    <div class="bike-stats">
                        <div class="bike-stat">
                            <div class="bike-stat-value">${a.type || '—'}</div>
                            <div class="bike-stat-label">Type</div>
                        </div>
                        <div class="bike-stat">
                            <div class="bike-stat-value">${a.training_load != null ? this.fmt(a.training_load, 0) : '—'}</div>
                            <div class="bike-stat-label">Load</div>
                        </div>
                        <div class="bike-stat">
                            <div class="bike-stat-value">${a.avg_hr_bpm != null ? this.fmt(a.avg_hr_bpm, 0) : '—'}</div>
                            <div class="bike-stat-label">Avg HR</div>
                        </div>
                        <div class="bike-stat">
                            <div class="bike-stat-value">${a.aerobic_te != null ? this.fmt(a.aerobic_te, 1) : '—'}</div>
                            <div class="bike-stat-label">Aerobic TE</div>
                        </div>
                    </div>
                    <p class="muted" style="margin:0.75rem 0 0;">${a.start_local || ''}</p>
                </div>
            `).join('');
        }

        root.classList.remove('hidden');
        document.getElementById('garmin-empty').classList.add('hidden');
    }
};

class GarminCoachUI {
    constructor() {
        this.bind();
        this.bootstrap();
    }

    bind() {
        const btn = document.getElementById('garmin-refresh-btn');
        if (btn) btn.addEventListener('click', () => this.refresh());
        const days = document.getElementById('garmin-days');
        if (days) days.value = String(GARMIN_CONFIG.DEFAULT_DAYS || 14);
    }

    async bootstrap() {
        // Auto-load on page open so GitHub Pages shows data immediately.
        await this.refresh();
    }

    async refresh() {
        const status = document.getElementById('garmin-status');
        const err = document.getElementById('garmin-error');
        const days = parseInt(document.getElementById('garmin-days')?.value || '14', 10);
        err?.classList.add('hidden');
        status.textContent = 'Loading Garmin coaching data…';
        try {
            const snap = await GarminCoach.load(days);
            GarminCoach.display(snap);
            status.textContent = snap._source === 'live'
                ? 'Updated from live Garmin API.'
                : 'Showing cached coach.json (set PROXY_BASE or run the FastAPI app for live data).';
        } catch (e) {
            console.error(e);
            status.textContent = '';
            if (err) {
                err.textContent = e.message || String(e);
                err.classList.remove('hidden');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (typeof GARMIN_CONFIG !== 'undefined') {
        new GarminCoachUI();
    }
});
