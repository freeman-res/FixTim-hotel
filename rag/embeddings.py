
from ollama import Client
EMBEDDING_MODEL = "bge-m3"
OLLAMA_HOST = "http://127.0.0.1:11434"
class Embedder:
    # Обёртка над Ollama embed API
    def __init__(self, model_name: str = EMBEDDING_MODEL, host: str = OLLAMA_HOST):
        self.client = Client(host=host)
        self.model_name = model_name
    def encode(self, texts: list[str]) -> list[list[float]]:
        #Превращает список текстов в список векторов.
        if not texts:
            return []
        response = self.client.embed(
            model=self.model_name,
            input=texts,
        )
        #  приведение к float 
        return [[float(x) for x in vec] for vec in response["embeddings"]]