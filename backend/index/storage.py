import json

def save_index(index_data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    
def load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        # index_data = json.load(f)
        return json.load(f)