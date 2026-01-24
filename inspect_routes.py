from api import app
from fastapi.routing import APIRoute

def inspect_routes():
    print("Registered Routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"{route.methods} {route.path}")

if __name__ == "__main__":
    inspect_routes()
