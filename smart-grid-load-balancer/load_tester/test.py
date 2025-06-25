import requests
import json
import time
import random
import threading
from datetime import datetime, timedelta
import sys

CHARGE_REQUEST_URL = "http://localhost:8000/charge"
LOAD_BALANCER_URL = "http://localhost:8080/status"
TOTAL_REQUESTS = 100
CONCURRENT_THREADS = 10
RUSH_HOUR_DURATION = 60  

stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'rejected_requests': 0,
    'response_times': [],
    'start_time': None,
    'end_time': None
}

stats_lock = threading.Lock()

def log_with_timestamp(message):
    """Print message with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def generate_charging_request():
    """Generate a realistic EV charging request"""
    vehicle_id = f"EV_{random.randint(1000, 9999)}"
    
    charge_amounts = [7, 11, 22, 50, 100, 150]  
    charge_amount = random.choice(charge_amounts)
    
    priority_choices = ['low', 'normal', 'normal', 'normal', 'high']
    priority = random.choice(priority_choices)
    
    return {
        'vehicle_id': vehicle_id,
        'charge_amount': charge_amount,
        'priority': priority,
        'request_time': datetime.now().isoformat()
    }

def send_charge_request():
    """Send a single charge request and track statistics"""
    global stats
    
    try:
        request_data = generate_charging_request()
        start_time = time.time()
        
        response = requests.post(
            CHARGE_REQUEST_URL,
            json=request_data,
            timeout=30
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        with stats_lock:
            stats['total_requests'] += 1
            stats['response_times'].append(response_time)
            
            if response.status_code == 200:
                stats['successful_requests'] += 1
                result = response.json()
                log_with_timestamp(f"✓ Vehicle {request_data['vehicle_id']} charged at "
                                 f"{result.get('substation_id', 'unknown')} "
                                 f"({request_data['charge_amount']}kW, {response_time:.2f}s)")
            elif response.status_code == 503:
                stats['rejected_requests'] += 1
                log_with_timestamp(f"⚠ Vehicle {request_data['vehicle_id']} rejected - "
                                 f"insufficient capacity ({response_time:.2f}s)")
            else:
                stats['failed_requests'] += 1
                log_with_timestamp(f"✗ Vehicle {request_data['vehicle_id']} failed - "
                                 f"HTTP {response.status_code} ({response_time:.2f}s)")
                
    except requests.RequestException as e:
        with stats_lock:
            stats['total_requests'] += 1
            stats['failed_requests'] += 1
        log_with_timestamp(f"✗ Request failed: {str(e)}")
    except Exception as e:
        with stats_lock:
            stats['total_requests'] += 1
            stats['failed_requests'] += 1
        log_with_timestamp(f"✗ Unexpected error: {str(e)}")

def worker_thread():
    """Worker thread that continuously sends requests during rush hour"""
    while True:
        current_time = datetime.now()
        if stats['end_time'] and current_time >= stats['end_time']:
            break
        
        send_charge_request()
        
        time.sleep(random.uniform(0.1, 2.0))

def monitor_system_status():
    """Monitor and log system status during load testing"""
    log_with_timestamp("Starting system monitoring...")
    
    while True:
        current_time = datetime.now()
        if stats['end_time'] and current_time >= stats['end_time']:
            break
        
        try:
            response = requests.get(LOAD_BALANCER_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                loads = data.get('substation_loads', {})
                load_info = ', '.join([f"{k}: {v}" for k, v in loads.items()])
                log_with_timestamp(f"📊 Substation loads: {load_info}")
            else:
                log_with_timestamp("⚠ Failed to get load balancer status")
        except Exception as e:
            log_with_timestamp(f"⚠ Error monitoring system: {str(e)}")
        
        time.sleep(10) 

def print_final_statistics():
    """Print comprehensive test results"""
    print("\n" + "="*80)
    print("LOAD TEST RESULTS")
    print("="*80)
    
    duration = (stats['end_time'] - stats['start_time']).total_seconds()
    
    print(f"Test Duration: {duration:.1f} seconds")
    print(f"Total Requests: {stats['total_requests']}")
    print(f"Successful Requests: {stats['successful_requests']} ({stats['successful_requests']/stats['total_requests']*100:.1f}%)")
    print(f"Rejected Requests: {stats['rejected_requests']} ({stats['rejected_requests']/stats['total_requests']*100:.1f}%)")
    print(f"Failed Requests: {stats['failed_requests']} ({stats['failed_requests']/stats['total_requests']*100:.1f}%)")
    print(f"Requests per Second: {stats['total_requests']/duration:.2f}")
    
    if stats['response_times']:
        avg_response_time = sum(stats['response_times']) / len(stats['response_times'])
        min_response_time = min(stats['response_times'])
        max_response_time = max(stats['response_times'])
        
        print(f"\nResponse Times:")
        print(f"Average: {avg_response_time:.3f}s")
        print(f"Minimum: {min_response_time:.3f}s")
        print(f"Maximum: {max_response_time:.3f}s")
    
    print("\n" + "="*80)

def simulate_rush_hour():
    """Simulate a rush hour of EV charging requests"""
    print("🚗 Smart Grid Load Balancer - Rush Hour Simulation")
    print("="*60)
    
    stats['start_time'] = datetime.now()
    stats['end_time'] = stats['start_time'] + timedelta(seconds=RUSH_HOUR_DURATION)
    
    log_with_timestamp(f"Starting {RUSH_HOUR_DURATION}s rush hour simulation with {CONCURRENT_THREADS} concurrent threads")
    
    monitor_thread = threading.Thread(target=monitor_system_status, daemon=True)
    monitor_thread.start()
    
    threads = []
    for i in range(CONCURRENT_THREADS):
        thread = threading.Thread(target=worker_thread, daemon=True)
        thread.start()
        threads.append(thread)
        log_with_timestamp(f"Started worker thread {i+1}")
    
    for thread in threads:
        thread.join()
    
    log_with_timestamp("Rush hour simulation completed!")
    
    print_final_statistics()

def run_simple_test():
    """Run a simple test with a few requests"""
    print("🔧 Running simple connectivity test...")
    
    for i in range(5):
        log_with_timestamp(f"Sending test request {i+1}/5")
        request_data = generate_charging_request()
        
        try:
            response = requests.post(CHARGE_REQUEST_URL, json=request_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                log_with_timestamp(f"✓ Success: {result.get('substation_id', 'unknown')}")
            else:
                log_with_timestamp(f"⚠ HTTP {response.status_code}: {response.text}")
        except Exception as e:
            log_with_timestamp(f"✗ Error: {str(e)}")
        
        time.sleep(2)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "simple":
        run_simple_test()
    else:
        simulate_rush_hour()