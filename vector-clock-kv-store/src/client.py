import requests
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: python client.py <node_url> <command> [arguments]")
        return
    
    node_url = sys.argv[1]
    command = sys.argv[2]
    
    if command == 'write':
        if len(sys.argv) < 5:
            print("Usage: python client.py <node_url> write <key> <value>")
            return
        key = sys.argv[3]
        value = sys.argv[4]
        response = requests.post(f"{node_url}/write", json={'key': key, 'value': value})
        print(response.json())
    elif command == 'read':
        if len(sys.argv) < 4:
            print("Usage: python client.py <node_url> read <key>")
            return
        key = sys.argv[3]
        response = requests.get(f"{node_url}/read/{key}")
        print(response.json())
    else:
        print("Invalid command")

if __name__ == '__main__':
    main()