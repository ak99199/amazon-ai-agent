"""AWS Lambda Function URL adapter for the separate web dashboard function."""
from mangum import Mangum
from main import app
handler = Mangum(app, lifespan="off")
