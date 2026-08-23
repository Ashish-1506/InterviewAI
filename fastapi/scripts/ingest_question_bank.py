from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.services.faiss_index import QuestionBankIndex
from app.services.question_bank import QuestionBankLoader


def main():
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embedding in this build")

    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)

    loader = QuestionBankLoader(settings=settings)
    questions = loader.load()
    documents = loader.to_documents(questions)

    index = QuestionBankIndex(settings=settings)
    _ = index.load_or_build(embeddings, documents)

    print("FAISS question bank ready.")


if __name__ == "__main__":
    _ = argparse.ArgumentParser().parse_args()
    main()


