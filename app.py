from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from config import DB_CONFIG
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta
import requests
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# Groq API configuration
GROQ_API_KEY = os.environ.get('Groq_API_Key')
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/update_stock', methods=['POST'])
def update_stock():
    data = request.json
    product_id = data['product_id']
    quantity = data['quantity']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO stocks (product_id, quantity) VALUES (%s, %s) ON DUPLICATE KEY UPDATE quantity = %s",
                       (product_id, quantity, quantity))
        conn.commit()
        return jsonify({"message": "Stock updated successfully"})
    except mysql.connector.Error as err:
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
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO sales (product_id, quantity, date) VALUES (%s, %s, %s)",
                       (product_id, quantity, date))
        conn.commit()
        return jsonify({"message": "Sales data updated successfully"})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/analyze_inventory', methods=['GET'])
def analyze_inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT product_id, quantity FROM stocks")
        stocks = {row['product_id']: row['quantity'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT product_id, quantity, date FROM sales")
        sales = cursor.fetchall()
        
        results = {}
        for product_id in stocks:
            current_stock = stocks[product_id]
            product_sales = [sale for sale in sales if sale['product_id'] == product_id]
            
            if len(product_sales) > 30:
                df = pd.DataFrame(product_sales)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                
                model = RandomForestRegressor()
                X = df.index.astype(int).values.reshape(-1, 1)
                y = df['quantity'].values
                model.fit(X, y)
                
                last_date = df.index[-1]
                next_week = pd.date_range(start=last_date + timedelta(days=1), periods=7)
                X_pred = next_week.astype(int).values.reshape(-1, 1)
                forecast = model.predict(X_pred)
                
                expected_sales = sum(forecast)
                if current_stock > 2 * expected_sales:
                    status = "Overstocked"
                    suggestion = "Consider offering a discount"
                elif current_stock < expected_sales:
                    status = "Understocked"
                    suggestion = "Reorder soon"
                else:
                    status = "Optimal"
                    suggestion = "No action needed"
                
                results[product_id] = {
                    "status": status,
                    "current_stock": current_stock,
                    "expected_sales": expected_sales,
                    "suggestion": suggestion
                }
            else:
                results[product_id] = {
                    "status": "Insufficient data",
                    "current_stock": current_stock,
                    "suggestion": "Collect more sales data"
                }
        
        return jsonify({"inventory_analysis": results})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

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
            {"role": "system", "content": "You are a helpful assistant focused on supply chain management (SCM) , business , incresing sales and rectify loss, how to sell the product,rectifying overstocking related topics. This includes sales, marketing, inventory management, demand forecasting, supply chain operations, logistics, and related areas. Provide detailed and practical advice on these topics."},
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
        return jsonify({"error": f"Error communicating with Groq AI: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)