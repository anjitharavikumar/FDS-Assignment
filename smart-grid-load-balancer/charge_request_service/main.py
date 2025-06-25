from flask import Flask, request, jsonify
import requests
import logging
import os
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOAD_BALANCER_URL = os.getenv('LOAD_BALANCER_URL', 'http://load_balancer:8080')

@app.route('/charge', methods=['POST'])
def charge_request():
    """
    Handles incoming EV charging requests and forwards them to the load balancer
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['vehicle_id', 'charge_amount', 'priority']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        data['timestamp'] = datetime.now().isoformat()
        
        logger.info(f"Received charge request for vehicle {data['vehicle_id']}")
        
        response = requests.post(
            f"{LOAD_BALANCER_URL}/route_charge",
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Charge request routed successfully to {result.get('substation_id')}")
            return jsonify(result), 200
        else:
            logger.error(f"Load balancer error: {response.status_code}")
            return jsonify({'error': 'Failed to route charge request'}), 500
            
    except requests.RequestException as e:
        logger.error(f"Connection error to load balancer: {str(e)}")
        return jsonify({'error': 'Load balancer unavailable'}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'charge_request_service'}), 200

@app.route('/status', methods=['GET'])
def status():
    """Service status endpoint"""
    try:
        response = requests.get(f"{LOAD_BALANCER_URL}/health", timeout=5)
        lb_status = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        lb_status = "unreachable"
    
    return jsonify({
        'service': 'charge_request_service',
        'status': 'running',
        'load_balancer_status': lb_status,
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)