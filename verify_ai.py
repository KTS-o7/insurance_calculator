import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_ai_insight():
    url = "http://127.0.0.1:5000/api/get-ai-insight"
    payload = {
        "context": "comparison",
        "metrics": {
            "years": 20,
            "annual_outflow": 100000,
            "endowment_value": 2500000,
            "btir_value": 4500000,
            "endowment_irr": 5.5,
            "opportunity_cost": 2000000,
            "return_rate": 12.0
        }
    }
    
    print(f"Testing API at {url} with payload: {payload}")
    
    # Note: This requires the flask app to be running.
    # Since I cannot guarantee background processes persist robustly here, 
    # I will rely on code inspection if this fails.
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response:", response.json())
        else:
            print("Error Response:", response.text)
    except Exception as e:
        print(f"Request failed: {e}")
        print("Note: If the server is not running, this is expected.")

if __name__ == "__main__":
    test_ai_insight()
