from ssh_server import start_ssh_server
from llm import LLM

MODEL_NAME = "NousResearch/Meta-Llama-3-8B-Instruct"

if __name__ == "__main__":
    llama = LLM(MODEL_NAME)
    print("Loaded LLM — starting SSH honeypot...")
    start_ssh_server(llama)
