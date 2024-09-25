import os
from llama_index.core import (VectorStoreIndex, StorageContext,
                              load_index_from_storage)
from llama_index.readers.file import (
    DocxReader,
    HWPReader,
    PDFReader,
    EpubReader,
    FlatReader,
    HTMLTagReader,
    IPYNBReader,
    MarkdownReader,
    MboxReader,
    PptxReader,
    PandasCSVReader,
    XMLReader,
)
from pathlib import Path
import yaml

file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))

from backend.third_party import *
from backend.third_party_embedding import *
from backend.gpt import *


file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)

class LlamaIndexer():

    def __init__(self, username) -> None:
        if global_config.get("backend").get("provider") == "ollama":
            from backend.ollama import ollama_model, ollama_embed_model
            self.llm = ollama_model
            self.embed_model = ollama_embed_model
        elif global_config.get("backend").get("provider") == "deepseek":
            self.llm = client_deepseek_llama_index
        elif global_config.get("backend").get("provider") == "qwen":
            self.llm = client_qwen_llama_index
            self.embed_model = dashscope_embedder
        elif global_config.get("backend").get("provider") == "glm":
            self.llm = client_glm_llama_index
        elif global_config.get("backend").get("provider") == "hunyuan":
            self.llm = client_hunyuan_llama_index
        elif global_config.get("backend").get("provider") == "spark":
            self.llm = client_spark_llama_index
        elif global_config.get("backend").get("provider") == "ernie":
            raise NotImplementedError("ERNIE backend for llama_index not implemented")
        
        self.username = username

        self.user_directory = os.path.join(project_path, "userfiles", self.username)
        if not os.path.exists(self.user_directory):
            os.makedirs(self.user_directory)

        self.persist_dir = os.path.join(self.user_directory, "storage")
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)

        self.indexed_files_record_path = os.path.join(self.user_directory, "indexed_files.txt")
        self.indexed_files_record = set()

        try:
            self.index = VectorStoreIndex([], embed_model=self.embed_model)
            print("Indexer initialized successfully.")
        except Exception as e:
            print(f"Error initializing indexer: {e}")

        self.file_readers = {
            ".pdf": PDFReader(),
            ".docx": DocxReader(),
            ".hwp": HWPReader(),
            ".epub": EpubReader(),
            ".txt": FlatReader(),
            ".html": HTMLTagReader(),
            ".ipynb": IPYNBReader(),
            ".md": MarkdownReader(),
            ".mbox": MboxReader(),
            ".pptx": PptxReader(),
            ".csv": PandasCSVReader(),
            ".xml": XMLReader(),
        }

    def load_indexed_files(self):
        if os.path.exists(self.indexed_files_record_path):
            with open(self.indexed_files_record_path, "r") as f:
                self.indexed_files_record = set(line.strip() for line in f)

    def save_indexed_files(self):
        with open(self.indexed_files_record_path, "w") as f:
            for file in self.indexed_files_record:
                f.write(file + "\n")

    def get_index(self):
        if os.listdir(self.persist_dir):
            storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)
            self.index = load_index_from_storage(storage_context, embed_model=self.embed_model)
        else:
            self.index = VectorStoreIndex([], embed_model=self.embed_model)

    def perform_llama_index_embedding(self, file_path):
        file_extension = os.path.splitext(file_path)[1].lower()
        reader = self.file_readers.get(file_extension)
        if reader:
            documents = reader.load_data(Path(file_path))
            for doc in documents:
                self.index.insert(doc)
            # Persist the updated index
            self.index.storage_context.persist(persist_dir=self.persist_dir)

    def update_index_with_new_files(self, new_files):
        self.load_indexed_files()
        for file_path in new_files:
            if file_path not in self.indexed_files_record:
                self.perform_llama_index_embedding(file_path)
                self.indexed_files_record.add(file_path)
        self.save_indexed_files()

    def query(self, query):
        self.get_index()
        query_engine = self.index.as_query_engine(llm=self.llm)
        response = query_engine.query(query)
        # print(response.source_nodes)
        return response