import mysql.connector
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "court_data"),
            connect_timeout=5
        )
        logger.info("Database connection established")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Database connection failed: {err}")
        return None

def log_query(court_complex, case_type, case_number, filing_year, raw_response):
    """Log a query to the database"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            logger.warning("Skipping database log: No connection")
            return False
            
        cursor = conn.cursor()
        
        query = """
        INSERT INTO queries (
            court_complex, 
            case_type, 
            case_number, 
            filing_year, 
            raw_response,
            timestamp
        ) VALUES (%s, %s, %s, %s, %s, NOW())
        """
        
        params = (
            court_complex, 
            case_type, 
            case_number, 
            filing_year, 
            raw_response
        )
        
        cursor.execute(query, params)
        conn.commit()
        logger.info("Query logged successfully")
        return True
        
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    finally:
        try:
            if cursor:
                cursor.close()
        except:
            pass
        try:
            if conn and conn.is_connected():
                conn.close()
        except:
            pass