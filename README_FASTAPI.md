# FastAPI Version - Reddit SaaS Idea Finder

This is the FastAPI version of the Reddit SaaS Idea Finder, replacing the Streamlit frontend with a traditional web application.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Environment Variables
Create a `.env` file with your credentials:
```bash
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent
OPENAI_API_KEY=your_openai_api_key
```

### 3. Run the FastAPI App
```bash
python main_fastapi.py
```

The app will be available at: http://localhost:8000

## 📁 File Structure

```
├── main_fastapi.py          # FastAPI application
├── templates/
│   ├── index.html          # Main form page
│   └── results.html        # Results display page
├── static/                 # Static files (CSS, JS, images)
├── main.py                 # Original scraping pipeline
└── requirements.txt        # Dependencies
```

## 🔧 Features

- **Web Form**: Clean HTML form for subreddit input
- **Scraping Pipeline**: Uses the same `run_pipeline()` function from `main.py`
- **Results Display**: Beautiful HTML results page with:
  - Problem/opportunity analysis
  - Target market identification
  - Solution proposals
  - Tech stack recommendations
  - MVP features
  - Development time estimates
  - Cursor playbook prompts
- **Copy Functionality**: Copy playbook prompts to clipboard
- **Responsive Design**: Works on desktop and mobile

## 🌐 API Endpoints

- `GET /` - Display the main form
- `POST /scrape` - Run the scraping pipeline and show results

## 🎨 Customization

### Styling
- Edit CSS in the `<style>` sections of the HTML templates
- Add external CSS files to the `static/` directory
- Modify the templates in `templates/` directory

### Functionality
- Modify `main_fastapi.py` to add new endpoints
- Update the scraping parameters in the form
- Add new result display sections in `results.html`

## 🚀 Deployment

### Local Development
```bash
python main_fastapi.py
```

### Production Deployment
```bash
# Using uvicorn directly
uvicorn main_fastapi:app --host 127.0.0.1 --port 8000

# Using gunicorn (recommended for production)
pip install gunicorn
gunicorn main_fastapi:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main_fastapi:app", "--host", "127.0.0.1", "--port", "8000"]
```

## 🔍 Testing

Run the test script to verify the app works:
```bash
python test_fastapi.py
```

## 📊 Comparison with Streamlit Version

| Feature | Streamlit | FastAPI |
|---------|-----------|---------|
| Frontend | Streamlit components | HTML/CSS/JS |
| Deployment | Streamlit Cloud | Any web server |
| Customization | Limited | Full control |
| Performance | Good | Excellent |
| Source Code | Visible in browser | Hidden |
| Styling | Streamlit theme | Custom CSS |

## 🎯 Next Steps

1. **Add Authentication**: Integrate the existing auth systems
2. **Add Quota Management**: Implement user limits
3. **Add Database Integration**: Store results in Supabase
4. **Add User Dashboard**: View historical results
5. **Add Export Features**: Download results as JSON/CSV

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in `main_fastapi.py`
2. **Missing dependencies**: Run `pip install -r requirements.txt`
3. **Environment variables**: Make sure `.env` file is properly configured
4. **Template errors**: Check that `templates/` directory exists

### Debug Mode
```bash
uvicorn main_fastapi:app --reload --host 127.0.0.1 --port 8000
```

## 📝 License

MIT License - same as the original project. 