from flask import Flask, request, render_template, session
from scraper import fetch_case_details
from db import log_query
import os
import time
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')

@app.route('/')
def home():
    session.pop('form_data', None)
    session.pop('search_start_time', None)
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    start_time = time.time()
    session['search_start_time'] = start_time
    
    # Get form data
    form_data = {
        'est_code': request.form['est_code'],
        'case_type': request.form['case_type'],
        'reg_no': request.form['reg_no'],
        'reg_year': request.form['reg_year']
    }
    session['form_data'] = form_data
    
    # Get CAPTCHA if available
    captcha = request.form.get('captcha', None)
    
    # Fetch case details
    logger.info(f"Starting search: {form_data}")
    result = fetch_case_details(
        form_data['est_code'],
        form_data['case_type'],
        form_data['reg_no'],
        form_data['reg_year'],
        captcha
    )
    
    # Calculate processing time
    processing_time = round(time.time() - start_time, 2)
    logger.info(f"Search completed in {processing_time} seconds")
    
    # Log query to database
    try:
        log_query(
            court_complex=form_data['est_code'],
            case_type=form_data['case_type'],
            case_number=form_data['reg_no'],
            filing_year=form_data['reg_year'],
            raw_response=json.dumps(result)
        )
    except Exception as db_error:
        logger.error(f"Database logging failed: {db_error}")
    
    # Handle response states
    if result.get('status') == 'captcha_required':
        logger.info("CAPTCHA required")
        return render_template("captcha.html", 
                              captcha_image=result['captcha_image'],
                              form_data=form_data)
    
    elif result.get('status') == 'invalid_captcha':
        logger.warning("Invalid CAPTCHA")
        return render_template("captcha.html", 
                              captcha_image=result.get('captcha_image', ''),
                              form_data=form_data,
                              error="Invalid CAPTCHA. Please try again.")
    
    elif result.get('status') == 'success':
        logger.info(f"Found {len(result['results'])} results")
        return render_template("result.html", 
                              results=result['results'],
                              processing_time=processing_time)
    
    elif result.get('status') == 'not_found':
        logger.info("No results found")
        return render_template("error.html", 
                              error="No cases found matching your criteria",
                              form_data=form_data)
    
    else:
        error_msg = result.get('message', 'An unexpected error occurred')
        logger.error(f"Search error: {error_msg}")
        return render_template("error.html", 
                              error=error_msg,
                              form_data=form_data)

@app.route('/retry', methods=['POST'])
def retry():
    form_data = session.get('form_data', {})
    return render_template('index.html', form_data=form_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)