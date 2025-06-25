import json
import threading
from flask import Flask, request, jsonify
from collections import defaultdict

app = Flask(__name__)

class VectorClock:
    def __init__(self, node_id, node_count):
        self.node_id = node_id
        self.clock = [0] * node_count 
        
    def increment(self):
        self.clock[self.node_id] += 1
        
    def update(self, received_clock):
        for i in range(len(self.clock)):
            self.clock[i] = max(self.clock[i], received_clock[i])
        
    def __str__(self):
        return str(self.clock)

class KVStore:
    def __init__(self, node_id, node_count):
        self.node_id = node_id
        self.store = {}
        self.vector_clock = VectorClock(node_id, node_count)
        self.pending_messages = []
        self.lock = threading.Lock()
        
    def handle_local_write(self, key, value):
        with self.lock:
            self.vector_clock.increment()
            self.store[key] = value
            return {
                'key': key,
                'value': value,
                'vector_clock': self.vector_clock.clock,
                'node_id': self.node_id
            }
            
    def handle_received_write(self, message):
        with self.lock:
            # Check if we can apply this message immediately
            can_apply = True
            for i in range(len(self.vector_clock.clock)):
                if i != message['node_id'] and self.vector_clock.clock[i] < message['vector_clock'][i]:
                    can_apply = False
                    break
            
            if can_apply:
                self.store[message['key']] = message['value']
                self.vector_clock.update(message['vector_clock'])
                # Check if pending messages can now be applied
                self.process_pending_messages()
            else:
                self.pending_messages.append(message)
                
    def process_pending_messages(self):
        for msg in list(self.pending_messages):
            can_apply = True
            for i in range(len(self.vector_clock.clock)):
                if i != msg['node_id'] and self.vector_clock.clock[i] < msg['vector_clock'][i]:
                    can_apply = False
                    break
            if can_apply:
                self.store[msg['key']] = msg['value']
                self.vector_clock.update(msg['vector_clock'])
                self.pending_messages.remove(msg)
                self.process_pending_messages()  

kv_store = KVStore(0, 3)

@app.route('/write', methods=['POST'])
def write_local():
    data = request.json
    message = kv_store.handle_local_write(data['key'], data['value'])
    return jsonify(message)

@app.route('/replicate', methods=['POST'])
def replicate():
    message = request.json
    kv_store.handle_received_write(message)
    return jsonify({'status': 'success'})

@app.route('/read/<key>', methods=['GET'])
def read(key):
    return jsonify({
        'key': key,
        'value': kv_store.store.get(key),
        'vector_clock': kv_store.vector_clock.clock
    })

if __name__ == '__main__':
    import os
    node_id = int(os.getenv('NODE_ID', 0))
    kv_store.node_id = node_id
    kv_store.vector_clock = VectorClock(node_id, 3)
    app.run(host='0.0.0.0', port=5000)