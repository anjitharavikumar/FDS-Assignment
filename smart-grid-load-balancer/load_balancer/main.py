from flask import Flask, request, jsonify
import requests
import logging
import os
import time
import threading
from datetime import datetime
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUBSTATIONS = [
    {'id': 'substation_1', 'url': 'http://substation_1:8001'},
    {'id': 'substation_2', 'url': 'http://substation_2:8001'},
    {'id': 'substation_3', 'url': 'http://substation_3:8001'}
]

substation_loads = {}
for substation in SUBSTATIONS:
    substation_loads[substation['id']] = 0

load_lock = threading.Lock()

def parse_prometheus_metrics(metrics_text):
    """Parse Prometheus metrics text format"""
    current_load = 0
    for line in metrics_text.split('\n'):
        if line.startswith('substation_current_load'):
            match = re.search(r'substation_current_load\s+(\d+(?:\.\d+)?)', line)
            if match:
                current_load = float(match.group(1))
                break
    return current_load

def update_substation_loads():
    """Periodically update substation loads by polling their metrics"""
    while True:
        try:
            for substation in SUBSTATIONS:
                try:
                    response = requests.get(f"{substation['url']}/metrics", timeout=5)
                    if response.status_code == 200:
                        current_load = parse_prometheus_metrics(response.text)
                        with load_lock:
                            substation_loads[substation['id']] = current_load
                        logger.debug(f"Updated {substation['id']} load: {current_load}")
                    else:
                        logger.warning(f"Failed to get metrics from {substation['id']}")
                except requests.RequestException as e:
                    logger.error(f"Error polling {substation['id']}: {str(e)}")


            time.sleep(5) 
            
        except Exception as e:
            logger.error(f"Error in load update thread: {str(e)}")
            time.sleep(10) 

def get_least_loaded_substation():
    """Find the substation with the lowest current load"""
    with load_lock:
        if not substation_loads:
            return SUBSTATIONS[0]  
        min_load = float('inf')
        best_substation = None
        
        for substation in SUBSTATIONS:
            load = substation_loads.get(substation['id'], 0)
            if load < min_load:
                min_load = load
                best_substation = substation
        
        return best_substation if best_substation else SUBSTATIONS[0]

@app.route('/route_charge', methods=['POST'])
def route_charge():
    """Route charging request to the least loaded substation"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        best_substation = get_least_loaded_substation()
        
        logger.info(f"Routing charge request to {best_substation['id']} "
                   f"(load: {substation_loads.get(best_substation['id'], 0)})")
        
        response = requests.post(
            f"{best_substation['url']}/charge",
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            result['routed_by'] = 'load_balancer'
            result['substation_id'] = best_substation['id']
            result['substation_load_before'] = substation_loads.get(best_substation['id'], 0)
            return jsonify(result), 200
        else:
            logger.error(f"Substation {best_substation['id']} returned error: {response.status_code}")
            return jsonify({'error': 'Substation processing failed'}), 500
            
    except requests.RequestException as e:
        logger.error(f"Connection error to substation: {str(e)}")
        return jsonify({'error': 'Substation unavailable'}), 503
    except Exception as e:
        logger.error(f"Unexpected error in load balancer: {str(e)}")
        return jsonify({'error': 'Load balancer internal error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'load_balancer'}), 200

@app.route('/status', methods=['GET'])
def status():
    """Get current status of all substations"""
    with load_lock:
        return jsonify({
            'service': 'load_balancer',
            'substation_loads': dict(substation_loads),
            'timestamp': datetime.now().isoformat()
        }), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    """Expose load balancer metrics in Prometheus format"""
    with load_lock:
        metrics_text = "# HELP load_balancer_requests_total Total requests processed by load balancer\n"
        metrics_text += "# TYPE load_balancer_requests_total counter\n"
        metrics_text += "load_balancer_requests_total 1\n"
        
        for substation_id, load in substation_loads.items():
            metrics_text += f"# HELP substation_load Current load of substation {substation_id}\n"
            metrics_text += f"# TYPE substation_load gauge\n"
            metrics_text += f'substation_load{{substation_id="{substation_id}"}} {load}\n'
    
    return metrics_text, 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    load_thread = threading.Thread(target=update_substation_loads, daemon=True)
    load_thread.start()
    
    logger.info("Starting load balancer service...")
    app.run(host='0.0.0.0', port=8080, debug=False)