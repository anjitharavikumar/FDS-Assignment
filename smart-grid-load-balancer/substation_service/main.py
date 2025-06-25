from flask import Flask, request, jsonify
import logging
import os
import time
import threading
import random
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SUBSTATION_ID = os.getenv('SUBSTATION_ID', 'substation_unknown')
MAX_CAPACITY = int(os.getenv('MAX_CAPACITY', '100'))  # Maximum charging capacity
CHARGE_PROCESSING_TIME = int(os.getenv('CHARGE_PROCESSING_TIME', '10'))  # seconds

# Current load tracking
current_load = 0
charging_sessions = {}  # Store active charging sessions
load_lock = threading.Lock()

def simulate_charging_completion():
    """Background thread to simulate charging completion"""
    global current_load, charging_sessions
    
    while True:
        try:
            current_time = datetime.now()
            completed_sessions = []
            
            with load_lock:
                for session_id, session_data in charging_sessions.items():
                    if current_time >= session_data['end_time']:
                        completed_sessions.append(session_id)
                        current_load -= session_data['charge_amount']
                        logger.info(f"Charging completed for session {session_id}, "
                                  f"load reduced by {session_data['charge_amount']}")
                
                # Remove completed sessions
                for session_id in completed_sessions:
                    del charging_sessions[session_id]
                
                # Ensure load doesn't go negative
                if current_load < 0:
                    current_load = 0
            
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            logger.error(f"Error in charging completion thread: {str(e)}")
            time.sleep(5)

@app.route('/charge', methods=['POST'])
def process_charge():
    """Process a charging request"""
    global current_load, charging_sessions
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['vehicle_id', 'charge_amount', 'priority']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        charge_amount = float(data['charge_amount'])
        vehicle_id = data['vehicle_id']
        priority = data.get('priority', 'normal')
        
        with load_lock:
            # Check if we can handle this charge request
            if current_load + charge_amount > MAX_CAPACITY:
                logger.warning(f"Charge request rejected - would exceed capacity "
                             f"(current: {current_load}, requested: {charge_amount}, max: {MAX_CAPACITY})")
                return jsonify({
                    'error': 'Insufficient capacity',
                    'current_load': current_load,
                    'max_capacity': MAX_CAPACITY,
                    'available_capacity': MAX_CAPACITY - current_load
                }), 503
            
            # Accept the charging request
            session_id = f"{SUBSTATION_ID}_{vehicle_id}_{int(time.time())}"
            
            # Calculate charging duration based on amount and priority
            base_duration = CHARGE_PROCESSING_TIME
            if priority == 'high':
                duration = max(base_duration * 0.7, 5)  # 30% faster for high priority
            elif priority == 'low':
                duration = base_duration * 1.3  # 30% slower for low priority
            else:
                duration = base_duration
            
            # Add some randomness to simulate real-world variation
            duration = duration * (0.8 + random.random() * 0.4)  # ±20% variation
            
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=duration)
            
            # Update load and add session
            current_load += charge_amount
            charging_sessions[session_id] = {
                'vehicle_id': vehicle_id,
                'charge_amount': charge_amount,
                'priority': priority,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration
            }
            
            logger.info(f"Started charging session {session_id} for vehicle {vehicle_id}, "
                       f"amount: {charge_amount}, duration: {duration:.1f}s, "
                       f"new load: {current_load}")
        
        return jsonify({
            'status': 'accepted',
            'session_id': session_id,
            'substation_id': SUBSTATION_ID,
            'vehicle_id': vehicle_id,
            'charge_amount': charge_amount,
            'estimated_duration': duration,
            'start_time': start_time.isoformat(),
            'current_load': current_load,
            'max_capacity': MAX_CAPACITY
        }), 200
        
    except ValueError as e:
        return jsonify({'error': f'Invalid charge amount: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in charge processing: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/metrics', methods=['GET'])
def metrics():
    """Expose metrics in Prometheus format"""
    with load_lock:
        metrics_text = f"# HELP substation_current_load Current charging load of the substation\n"
        metrics_text += f"# TYPE substation_current_load gauge\n"
        metrics_text += f"substation_current_load {current_load}\n"
        
        metrics_text += f"# HELP substation_max_capacity Maximum capacity of the substation\n"
        metrics_text += f"# TYPE substation_max_capacity gauge\n"
        metrics_text += f"substation_max_capacity {MAX_CAPACITY}\n"
        
        metrics_text += f"# HELP substation_active_sessions Number of active charging sessions\n"
        metrics_text += f"# TYPE substation_active_sessions gauge\n"
        metrics_text += f"substation_active_sessions {len(charging_sessions)}\n"
        
        utilization = (current_load / MAX_CAPACITY) * 100 if MAX_CAPACITY > 0 else 0
        metrics_text += f"# HELP substation_utilization_percent Capacity utilization percentage\n"
        metrics_text += f"# TYPE substation_utilization_percent gauge\n"
        metrics_text += f"substation_utilization_percent {utilization:.2f}\n"
    
    return metrics_text, 200, {'Content-Type': 'text/plain'}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'substation_id': SUBSTATION_ID}), 200

@app.route('/status', methods=['GET'])
def status():
    """Get detailed status of the substation"""
    with load_lock:
        return jsonify({
            'substation_id': SUBSTATION_ID,
            'current_load': current_load,
            'max_capacity': MAX_CAPACITY,
            'utilization_percent': (current_load / MAX_CAPACITY) * 100 if MAX_CAPACITY > 0 else 0,
            'active_sessions': len(charging_sessions),
            'available_capacity': MAX_CAPACITY - current_load,
            'sessions': {k: {
                'vehicle_id': v['vehicle_id'],
                'charge_amount': v['charge_amount'],
                'priority': v['priority'],
                'remaining_time': (v['end_time'] - datetime.now()).total_seconds()
            } for k, v in charging_sessions.items()},
            'timestamp': datetime.now().isoformat()
        }), 200

if __name__ == '__main__':
    # Start the charging completion simulation thread
    completion_thread = threading.Thread(target=simulate_charging_completion, daemon=True)
    completion_thread.start()
    
    logger.info(f"Starting substation {SUBSTATION_ID} with capacity {MAX_CAPACITY}")
    app.run(host='0.0.0.0', port=8001, debug=False)