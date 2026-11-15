# 🚴‍♂️ Strava Bike Tracker

A beautiful web application that connects to your Strava account and shows how far you've ridden each of your bikes since any given date. Built with modern web technologies and designed for GitHub Pages hosting.

## ✨ Features

- **Strava Integration**: Secure OAuth authentication with Strava
- **Multi-Bike Tracking**: View distance for each of your registered bikes
- **Date Range Selection**: Analyze rides from any start date to any end date
- **Account Memory**: Remembers your last used Strava account
- **Beautiful UI**: Modern, responsive design with smooth animations
- **Detailed Stats**: Distance, rides, elevation, and averages for each bike
- **GitHub Pages Ready**: Easy deployment to GitHub Pages
- **Coach API**: `GET /api/coach` returns Garmin training/recovery JSON for AI coaching agents

## 🚀 Live Demo

Visit the live demo: [https://johan-karlsson.github.io/strava-wax-checker/]

## 📋 Prerequisites

Before you begin, you'll need:

1. A Strava account with bike data
2. A Strava API application (free to create)
3. A GitHub account for hosting

## ⚙️ Setup Instructions

### 1. Fork/Clone This Repository

```bash
git clone https://github.com/yourusername/strava-bike-tracker.git
cd strava-bike-tracker
```

### 2. Create a Strava API Application

1. Go to [Strava API Settings](https://www.strava.com/settings/api)
2. Click "Create App"
3. Fill in the application details:
   - **Application Name**: "Bike Tracker" (or your preferred name)
   - **Category**: "Other"
   - **Club**: Leave blank
   - **Website**: `https://yourusername.github.io/strava-bike-tracker/`
   - **Authorization Callback Domain**: `yourusername.github.io`
   - **Description**: "Track bike mileage from Strava data"

4. Note down your **Client ID** and **Client Secret**

### 3. Configure the Application

1. Open `config.js` in your text editor
2. Replace `YOUR_STRAVA_CLIENT_ID` with your actual Client ID from step 2
3. The `REDIRECT_URI` will automatically be set to your GitHub Pages URL

```javascript
CLIENT_ID: '12345', // Replace with your actual Client ID
```

### 4. Deploy to GitHub Pages

1. Push your changes to your GitHub repository:
```bash
git add .
git commit -m "Initial setup with Strava API configuration"
git push origin main
```

2. Go to your repository on GitHub
3. Navigate to **Settings** → **Pages**
4. Under "Source", select "Deploy from a branch"
5. Select the "main" branch and "/ (root)" folder
6. Click "Save"

Your app will be available at `https://yourusername.github.io/strava-bike-tracker/` in a few minutes.

## 🔧 Important Security Note

This application currently includes placeholder text for the Client Secret. For a production deployment, you should:

1. **Never expose your Client Secret in client-side code**
2. Set up a backend service (like Vercel, Netlify Functions, or AWS Lambda) to handle the OAuth token exchange
3. Update the token exchange endpoints to use your backend service

For development and personal use, you can temporarily add your Client Secret directly to the code, but **never commit it to a public repository**.

## 📱 How to Use

1. **Connect Strava**: Click "Connect Strava Account" and authorize the application
2. **Select Dates**: Choose your start and end dates for the analysis
3. **Get Data**: Click "Get Bike Data" to fetch your riding statistics
4. **View Results**: See distance, rides, and elevation for each bike
5. **Change Account**: Use "Change Account" to switch Strava accounts if needed

## 🤖 Garmin coach data (static page + API)

**Primary URL for AI agents / Copilot:**

[`https://johan-karlsson.github.io/strava-wax-checker/agent.json`](https://johan-karlsson.github.io/strava-wax-checker/agent.json)

Verified serving:

- `Content-Type: application/json; charset=utf-8`
- No auth / cookies / CAPTCHA
- Public GitHub Pages
- Compact payload (tens of KB, last ~14 days)

Markdown companion (often better for LLM retrieval):

[`https://johan-karlsson.github.io/strava-wax-checker/agent.md`](https://johan-karlsson.github.io/strava-wax-checker/agent.md)

`/agent/` is only a redirect helper to `agent.json`. Prefer **`agent.json`** or **`agent.md`** for retrieval.

The JSON includes AI-friendly top-level fields: `generated_at`, `athlete`, `summary`, `recent_activities`, plus detailed `daily` / `activities` / `aggregates`.

Refreshed about every 10 minutes by GitHub Actions (updates `coach.json`, `agent.json`, and `agent.md` through **UTC today**). GitHub may delay cron slightly under load. The Personal API key lives in `config.js` for the refresh job / local tools.

### Quick checks

```bash
curl -I https://johan-karlsson.github.io/strava-wax-checker/agent.json
curl -s https://johan-karlsson.github.io/strava-wax-checker/agent.json | head
curl -s https://johan-karlsson.github.io/strava-wax-checker/agent.md | head
```

### Local FastAPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set GARMIN_PERSONAL_API_KEY
npm run dev
curl -s 'http://127.0.0.1:8000/agent.json' | jq '.summary'
```

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/agent.json` | Coaching JSON (`application/json`) — use this for agents |
| `GET` | `/agent.md` | Markdown training summary — use this for LLM retrieval |
| `GET` | `/agent` | Redirect/helper page to `agent.json` |
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/coach` | Live Garmin fetch; refreshes `agent.json` / `agent.md` |
| `GET` | `/` | Strava wax-checker UI |

### Query parameters for `/api/coach`

- `days` (default `14`, max `92`)
- `start` / `end` — optional `YYYY-MM-DD`
- `max_activities` (default `200`)

CLI:

```bash
python3 garmin_coach.py --days 14 -o coach.json
cp coach.json agent.json
python3 -c "import json; from pathlib import Path; from garmin_coach import to_agent_markdown; p=Path('agent.json'); Path('agent.md').write_text(to_agent_markdown(json.loads(p.read_text())))"
```

## 🛠️ Technical Details

### Built With

- **HTML5** - Semantic markup and structure
- **CSS3** - Modern styling with CSS Grid and Flexbox
- **Vanilla JavaScript** - No frameworks, just pure JS
- **Strava API v3** - Official Strava REST API
- **FastAPI** - Coach API (`/api/coach`) over Garmin Personal API
- **Font Awesome** - Icons and visual elements
- **Inter Font** - Modern, readable typography

### Browser Support

- Chrome 60+
- Firefox 60+
- Safari 12+
- Edge 79+

### API Endpoints Used

- `GET /athlete` - User profile and bike information
- `GET /athlete/activities` - Activity data for date range analysis

## 🎨 Customization

### Changing Colors

Update the CSS custom properties in `style.css`:

```css
:root {
    --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --accent-gradient: linear-gradient(135deg, #fc6076 0%, #ff9a44 100%);
}
```

### Adding Features

The codebase is modular and easy to extend:

- `config.js` - Configuration and utility functions
- `script.js` - Main application logic
- `style.css` - All styling and responsive design

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔒 Privacy

This application:
- Only requests necessary Strava permissions (read activities and profile)
- Stores authentication tokens locally in your browser
- Does not send data to any third-party services
- Respects Strava's API terms of service

## 📞 Support

If you encounter any issues:

1. Check the browser console for error messages
2. Verify your Strava API credentials are correct
3. Ensure your redirect URI matches exactly
4. Open an issue on GitHub with details about the problem

## 🙏 Acknowledgments

- [Strava API](https://developers.strava.com/) for providing access to activity data
- [Font Awesome](https://fontawesome.com/) for the beautiful icons
- [Inter Font](https://rsms.me/inter/) for the clean typography

---

Made with ❤️ for the cycling community 
