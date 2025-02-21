# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from config import DB_CONFIG
from datetime import datetime
import requests
import os
import json
import logging
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

logging.basicConfig(level=logging.INFO)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

if not GROQ_API_KEY:
    logging.error("Groq API key is not set. Please set the GROQ_API_KEY environment variable.")
    exit(1)

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        logging.error(f"Error connecting to the database: {str(err)}")
        return None

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/update_stock', methods=['POST'])
def update_stock():
    data = request.json
    product_id = data['product_id']
    quantity = data['quantity']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT quantity FROM stocks WHERE product_id = %s", (product_id,))
        result = cursor.fetchone()
        
        if result:
            new_quantity = result[0] + quantity
            cursor.execute("UPDATE stocks SET quantity = %s WHERE product_id = %s", (new_quantity, product_id))
        else:
            cursor.execute("INSERT INTO stocks (product_id, quantity) VALUES (%s, %s)", (product_id, quantity))
        
        conn.commit()
        return jsonify({"message": "Stock updated successfully"})
    except mysql.connector.Error as err:
        logging.error(f"Error updating stock: {str(err)}")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/update_sales', methods=['POST'])
def update_sales():
    data = request.json
    product_id = data['product_id']
    quantity = data['quantity']
    date = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO sales (product_id, quantity, date) VALUES (%s, %s, %s)", (product_id, quantity, date))
        cursor.execute("UPDATE stocks SET quantity = quantity - %s WHERE product_id = %s", (quantity, product_id))
        conn.commit()
        return jsonify({"message": "Sales data updated and stock reduced successfully"})
    except mysql.connector.Error as err:
        conn.rollback()
        logging.error(f"Error updating sales: {str(err)}")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/analyze_inventory', methods=['GET'])
def analyze_inventory():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT s.product_id, s.quantity as current_stock, 
                   COALESCE(SUM(sa.quantity), 0) as total_sales,
                   MAX(sa.date) as last_sale_date
            FROM stocks s
            LEFT JOIN sales sa ON s.product_id = sa.product_id
            GROUP BY s.product_id, s.quantity
        """)
        inventory_data = cursor.fetchall()
        
        for item in inventory_data:
            item['current_stock'] = float(item['current_stock'])
            item['total_sales'] = float(item['total_sales'])
            if item['last_sale_date']:
                item['last_sale_date'] = item['last_sale_date'].strftime('%Y-%m-%d')
        
        analysis = get_groq_inventory_analysis(inventory_data)
        return jsonify(analysis)
    except mysql.connector.Error as err:
        logging.error(f"Error analyzing inventory: {str(err)}")
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in analyze_inventory: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    finally:
        cursor.close()
        conn.close()

def get_groq_inventory_analysis(inventory_data):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Analyze the following inventory data and provide insights and recommendations:
    {json.dumps(inventory_data, indent=2, cls=DecimalEncoder)}
    
    Consider the following aspects:
    1. Current stock levels
    2. Total sales
    3. Last sale date
    4. Potential overstocking or understocking
    5. Sales trends
    6. Recommendations for inventory management
    7. Strategies to boost sales for slow-moving items
    8. Overall business improvement suggestions
    
    Provide a concise analysis and actionable recommendations in markdown format.
    """
    
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {"role": "system", "content": "You are an AI assistant specialized in inventory management and business analysis. Provide concise responses in markdown format."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        analysis = response.json()['choices'][0]['message']['content']
        return {"analysis": analysis}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error communicating with Groq AI: {str(e)}")
        return {"error": "Failed to generate inventory analysis"}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding Groq AI response: {str(e)}")
        return {"error": "Error decoding Groq AI response"}
    except KeyError as e:
        logging.error(f"Unexpected response format from Groq AI: {str(e)}")
        return {"error": "Unexpected response format from Groq AI"}
    
@app.route('/transport_route', methods=['POST'])
def transport_route():
    data = request.json
    start_point = data['start']
    destination = data['destination']
    important_points = data.get('important_points', [])
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Given the starting point '{start_point}' and destination '{destination}', 
    suggest an optimized transportation route passing through important locations: {important_points}. 
    Explain the choice of this route in terms of efficiency, safety, and cost-effectiveness.
    Provide a concise analysis and actionable recommendations in markdown format.
    """
    
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {"role": "system", "content": "You are an AI assistant specialized in transportation management. Provide optimized routes with justifications.Provide concise responses in markdown format."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        route_info = response.json()['choices'][0]['message']['content']
        return jsonify({"route": route_info})
    except requests.exceptions.RequestException as e:
        logging.error(f"Error communicating with Groq AI: {str(e)}")
        return jsonify({"error": "Failed to get transport route"}), 500

@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.json
    user_message = data['message']
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant focused on supply chain management (SCM), business strategies, increasing sales, rectifying losses, selling products effectively, managing inventory, and related topics. Provide concise and practical advice on these areas, including specific strategies for selling various products. Format your response in markdown, using appropriate headers, lists, and emphasis."},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        ai_response = response.json()['choices'][0]['message']['content']
        return jsonify({"response": ai_response})
    except requests.exceptions.RequestException as e:
        error_message = f"Error communicating with Groq AI: {str(e)}"
        logging.error(error_message)
        return jsonify({"error": error_message}), 500
    except json.JSONDecodeError as e:
        error_message = f"Error decoding Groq AI response: {str(e)}"
        logging.error(error_message)
        return jsonify({"error": error_message}), 500
    except KeyError as e:
        error_message = f"Unexpected response format from Groq AI: {str(e)}"
        logging.error(error_message)
        return jsonify({"error": error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)