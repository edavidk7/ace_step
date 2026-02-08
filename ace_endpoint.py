from dotenv import load_dotenv
import os
import ngrok
import time
import json

load_dotenv(".ngrok_env")

# Get basic auth credentials from environment
auth_username = os.getenv("AUTH_USERNAME")
auth_password = os.getenv("AUTH_PASSWORD")

# Build traffic policy for basic auth
traffic_policy = None
if auth_username and auth_password:
    policy = {
        "on_http_request": [
            {
                "actions": [
                    {
                        "type": "basic-auth",
                        "config": {
                            "credentials": [
                                f"{auth_username}:{auth_password}"
                            ]
                        }
                    }
                ]
            }
        ]
    }
    traffic_policy = json.dumps(policy)
    print(f"Basic auth enabled for user: {auth_username}")
else:
    print("WARNING: No AUTH_USERNAME or AUTH_PASSWORD found in .ngrok_env. API will be unprotected!")

listener = ngrok.forward(
	# The port your app is running on.
  8001,
  authtoken=os.getenv("NGROK_AUTHTOKEN"),
  domain=os.getenv("NGROK_DOMAIN"),
	# Secure your endpoint with basic authentication
  traffic_policy=traffic_policy
)

# Output ngrok URL to console
print(f"Ingress established at {listener.url()}")

# Keep the listener alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Closing listener")
