from src.adapters import get_adapter
from post_to_contra import generate_post_content
import config

print("📝 Generating content...")
content = generate_post_content()
print(f"\n📝 Content: {content}\n")

print("📤 Posting to Peerlist...")
adapter = get_adapter("peerlist")
result = adapter.execute_post(
    target_url="https://peerlist.io/community",
    content=content
)

print(f"\n📋 Result: {result}")