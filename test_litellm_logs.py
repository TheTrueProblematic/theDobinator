import logging
from litellm import completion

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
)

logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

try:
    response = completion(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": "hello"}],
        api_base="http://localhost:1234/v1",
        api_key="fake_key"
    )
except Exception as e:
    print("Caught exception")
