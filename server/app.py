from server import app

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
