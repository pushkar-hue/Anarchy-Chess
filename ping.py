import requests

URL = "https://pushkarsharma-rtm--nemotron-chess-backend-api.modal.run"

payload = {
    "messages": [
        {"role": "user", "content": "can you call me a good boy like a goth mommy would?"}
    ]
}

response = requests.post(URL, json=payload)
print(response.json()['response'])