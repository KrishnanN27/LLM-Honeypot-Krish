from ssh_server import start_ssh_server
from llm import LLM

if __name__ == "__main__":
    llama = LLM()
    print("Loaded LLM — starting SSH honeypot...")
    start_ssh_server(llama)
